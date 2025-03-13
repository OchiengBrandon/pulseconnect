from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import (
    ResearchProject, ProjectMembership, ProjectTask, 
    ProjectDocument, ProjectInvitation
)
from .forms import (
    ResearchProjectForm, ProjectMembershipForm, ProjectTaskForm, 
    ProjectDocumentForm, ProjectInvitationForm
)
from accounts.models import User

class ProjectListView(LoginRequiredMixin, ListView):
    model = ResearchProject
    template_name = 'collaboration/project_list.html'
    context_object_name = 'projects'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        
        # Show projects the user is a member of or that are public
        queryset = ResearchProject.objects.filter(
            Q(owner=user) | Q(members=user) | Q(is_public=True)
        ).distinct()
        
        # Filter by status if provided
        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Search
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query)
            ).distinct()
        
        # Filter by involvement
        involvement = self.request.GET.get('involvement', '')
        if involvement == 'owner':
            queryset = queryset.filter(owner=user)
        elif involvement == 'member':
            queryset = queryset.filter(members=user).exclude(owner=user)
        elif involvement == 'public':
            queryset = queryset.filter(is_public=True).exclude(members=user)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['status_filter'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['involvement'] = self.request.GET.get('involvement', '')
        
        # Add status choices for filter
        context['status_choices'] = ResearchProject.STATUS_CHOICES
        
        return context


class ProjectDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = ResearchProject
    template_name = 'collaboration/project_detail.html'
    context_object_name = 'project'
    
    def test_func(self):
        project = self.get_object()
        user = self.request.user
        
        # Check if user has access to this project
        return (project.owner == user or 
                project.members.filter(id=user.id).exists() or 
                project.is_public)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        user = self.request.user
        
        # Get user's membership
        try:
            membership = ProjectMembership.objects.get(project=project, user=user)
            context['membership'] = membership
        except ProjectMembership.DoesNotExist:
            context['membership'] = None
        
        # Check if user can edit
        context['can_edit'] = (project.owner == user or 
                              (context['membership'] and context['membership'].can_edit))
        
        # Check if user can invite
        context['can_invite'] = (project.owner == user or 
                               (context['membership'] and context['membership'].can_invite))
        
        # Get project tasks
        context['tasks'] = ProjectTask.objects.filter(project=project)
        
        # Get project documents
        context['documents'] = ProjectDocument.objects.filter(project=project)
        
        # Get project members
        context['members'] = ProjectMembership.objects.filter(project=project)
        
        # Get pending invitations
        if context['can_invite']:
            context['pending_invitations'] = ProjectInvitation.objects.filter(
                project=project,
                status='pending'
            )
        
        return context


@method_decorator(login_required, name='dispatch')
class ProjectCreateView(CreateView):
    model = ResearchProject
    form_class = ResearchProjectForm
    template_name = 'collaboration/project_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Set owner
        form.instance.owner = self.request.user
        
        response = super().form_valid(form)
        
        # Add owner as a member with full permissions
        ProjectMembership.objects.create(
            project=self.object,
            user=self.request.user,
            role='coordinator',
            can_edit=True,
            can_invite=True
        )
        
        messages.success(self.request, _('Project created successfully!'))
        return response


@method_decorator(login_required, name='dispatch')
class ProjectUpdateView(UserPassesTestMixin, UpdateView):
    model = ResearchProject
    form_class = ResearchProjectForm
    template_name = 'collaboration/project_form.html'
    
    def test_func(self):
        project = self.get_object()
        user = self.request.user
        
        # Check if user can edit this project
        if project.owner == user:
            return True
        
        try:
            membership = ProjectMembership.objects.get(project=project, user=user)
            return membership.can_edit
        except ProjectMembership.DoesNotExist:
            return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Project updated successfully!'))
        return super().form_valid(form)


@login_required
def project_members(request, pk):
    """View and manage project members"""
    project = get_object_or_404(ResearchProject, pk=pk)
    
    # Check if user has access
    if not (project.owner == request.user or project.members.filter(id=request.user.id).exists()):
        return HttpResponseForbidden()
    
    # Check if user can edit members
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    memberships = ProjectMembership.objects.filter(project=project)
    
    return render(request, 'collaboration/project_members.html', {
        'project': project,
        'memberships': memberships,
        'can_edit': can_edit
    })


@login_required
@require_POST
def update_member_role(request, project_pk, user_pk):
    """Update a member's role and permissions"""
    project = get_object_or_404(ResearchProject, pk=project_pk)
    member = get_object_or_404(User, pk=user_pk)
    
    # Check if user is the owner
    if request.user != project.owner:
        return HttpResponseForbidden()
    
    # Cannot change the owner's membership
    if member == project.owner:
        messages.error(request, _('Cannot modify the project owner\'s role.'))
        return redirect('collaboration:project_members', pk=project.pk)
    
    try:
        membership = ProjectMembership.objects.get(project=project, user=member)
        
        role = request.POST.get('role')
        can_edit = request.POST.get('can_edit') == 'on'
        can_invite = request.POST.get('can_invite') == 'on'
        
        membership.role = role
        membership.can_edit = can_edit
        membership.can_invite = can_invite
        membership.save()
        
        messages.success(request, _('Member role updated successfully!'))
    except ProjectMembership.DoesNotExist:
        messages.error(request, _('Membership not found.'))
    
    return redirect('collaboration:project_members', pk=project.pk)


@login_required
@require_POST
def remove_member(request, project_pk, user_pk):
    """Remove a member from the project"""
    project = get_object_or_404(ResearchProject, pk=project_pk)
    member = get_object_or_404(User, pk=user_pk)
    
    # Check if user is the owner
    if request.user != project.owner:
        return HttpResponseForbidden()
    
    # Cannot remove the owner
    if member == project.owner:
        messages.error(request, _('Cannot remove the project owner.'))
        return redirect('collaboration:project_members', pk=project.pk)
    
    try:
        membership = ProjectMembership.objects.get(project=project, user=member)
        membership.delete()
        
        messages.success(request, _('Member removed successfully!'))
    except ProjectMembership.DoesNotExist:
        messages.error(request, _('Membership not found.'))
    
    return redirect('collaboration:project_members', pk=project.pk)


@login_required
def project_tasks(request, pk):
    """View and manage project tasks"""
    project = get_object_or_404(ResearchProject, pk=pk)
    
    # Check if user has access
    if not (project.owner == request.user or project.members.filter(id=request.user.id).exists()):
        return HttpResponseForbidden()
    
    # Check if user can edit tasks
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    # Process task form if submitted
    if request.method == 'POST' and can_edit:
        form = ProjectTaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            
            messages.success(request, _('Task created successfully!'))
            return redirect('collaboration:project_tasks', pk=project.pk)
    else:
        form = ProjectTaskForm(project=project)
    
    # Get tasks grouped by status
    tasks_by_status = {}
    for status, status_display in ProjectTask.STATUS_CHOICES:
        tasks_by_status[status] = ProjectTask.objects.filter(
            project=project,
            status=status
        ).order_by('due_date', '-priority')
    
    return render(request, 'collaboration/project_tasks.html', {
        'project': project,
        'tasks_by_status': tasks_by_status,
        'form': form,
        'can_edit': can_edit
    })


@login_required
@require_POST
def update_task_status(request, task_pk):
    """Update a task's status"""
    task = get_object_or_404(ProjectTask, pk=task_pk)
    project = task.project
    
    # Check if user has edit access
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    if not can_edit:
        return HttpResponseForbidden()
    
    new_status = request.POST.get('status')
    if new_status in dict(ProjectTask.STATUS_CHOICES).keys():
        task.status = new_status
        
        # If completing the task, set completed_at
        if new_status == 'completed':
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        
        task.save()
        
        messages.success(request, _('Task status updated successfully!'))
    else:
        messages.error(request, _('Invalid status.'))
    
    return redirect('collaboration:project_tasks', pk=project.pk)


@login_required
def edit_task(request, task_pk):
    """Edit a task"""
    task = get_object_or_404(ProjectTask, pk=task_pk)
    project = task.project
    
    # Check if user has edit access
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    if not can_edit:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = ProjectTaskForm(request.POST, instance=task, project=project)
        if form.is_valid():
            form.save()
            
            messages.success(request, _('Task updated successfully!'))
            return redirect('collaboration:project_tasks', pk=project.pk)
    else:
        form = ProjectTaskForm(instance=task, project=project)
    
    return render(request, 'collaboration/task_edit.html', {
        'form': form,
        'task': task,
        'project': project
    })


@login_required
@require_POST
def delete_task(request, task_pk):
    """Delete a task"""
    task = get_object_or_404(ProjectTask, pk=task_pk)
    project = task.project
    
    # Check if user has edit access
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    if not can_edit:
        return HttpResponseForbidden()
    
    task.delete()
    messages.success(request, _('Task deleted successfully!'))
    
    return redirect('collaboration:project_tasks', pk=project.pk)


@login_required
def project_documents(request, pk):
    """View and manage project documents"""
    project = get_object_or_404(ResearchProject, pk=pk)
    
    # Check if user has access
    if not (project.owner == request.user or project.members.filter(id=request.user.id).exists()):
        return HttpResponseForbidden()
    
    # Check if user can edit documents
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    # Process document form if submitted
    if request.method == 'POST' and can_edit:
        form = ProjectDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.project = project
            document.created_by = request.user
            document.save()
            
            messages.success(request, _('Document created successfully!'))
            return redirect('collaboration:project_documents', pk=project.pk)
    else:
        form = ProjectDocumentForm()
    
    # Get documents
    documents = ProjectDocument.objects.filter(project=project).order_by('-updated_at')
    
    return render(request, 'collaboration/project_documents.html', {
        'project': project,
        'documents': documents,
        'form': form,
        'can_edit': can_edit
    })


@login_required
def view_document(request, doc_pk):
    """View a project document"""
    document = get_object_or_404(ProjectDocument, pk=doc_pk)
    project = document.project
    
    # Check if user has access
    if not (project.owner == request.user or project.members.filter(id=request.user.id).exists()):
        return HttpResponseForbidden()
    
    return render(request, 'collaboration/document_view.html', {
        'document': document,
        'project': project
    })


@login_required
def edit_document(request, doc_pk):
    """Edit a project document"""
    document = get_object_or_404(ProjectDocument, pk=doc_pk)
    project = document.project
    
    # Check if user has edit access
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    if not can_edit:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = ProjectDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            # Increment version if content changed
            if form.cleaned_data['content'] != document.content or form.cleaned_data['file'] != document.file:
                document.version += 1
            
            document = form.save()
            
            messages.success(request, _('Document updated successfully!'))
            return redirect('collaboration:view_document', doc_pk=document.pk)
    else:
        form = ProjectDocumentForm(instance=document)
    
    return render(request, 'collaboration/document_edit.html', {
        'form': form,
        'document': document,
        'project': project
    })


@login_required
@require_POST
def delete_document(request, doc_pk):
    """Delete a project document"""
    document = get_object_or_404(ProjectDocument, pk=doc_pk)
    project = document.project
    
    # Check if user has edit access
    can_edit = (project.owner == request.user)
    if not can_edit:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_edit = membership.can_edit
        except ProjectMembership.DoesNotExist:
            can_edit = False
    
    if not can_edit:
        return HttpResponseForbidden()
    
    document.delete()
    messages.success(request, _('Document deleted successfully!'))
    
    return redirect('collaboration:project_documents', pk=project.pk)


@login_required
def project_invitations(request, pk):
    """Manage project invitations"""
    project = get_object_or_404(ResearchProject, pk=pk)
    
    # Check if user can invite
    can_invite = (project.owner == request.user)
    if not can_invite:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_invite = membership.can_invite
        except ProjectMembership.DoesNotExist:
            can_invite = False
    
    if not can_invite:
        return HttpResponseForbidden()
    
    # Process invitation form if submitted
    if request.method == 'POST':
        form = ProjectInvitationForm(request.POST, project=project, invited_by=request.user)
        if form.is_valid():
            invitation = form.save()
            
            # Send invitation email
            send_invitation_email(invitation, request)
            
            messages.success(request, _('Invitation sent successfully!'))
            return redirect('collaboration:project_invitations', pk=project.pk)
    else:
        form = ProjectInvitationForm(project=project, invited_by=request.user)
    
    # Get pending invitations
    invitations = ProjectInvitation.objects.filter(
        project=project,
        status='pending'
    ).order_by('-created_at')
    
    return render(request, 'collaboration/project_invitations.html', {
        'project': project,
        'invitations': invitations,
        'form': form
    })


def send_invitation_email(invitation, request):
    """Send invitation email"""
    context = {
        'invitation': invitation,
        'accept_url': request.build_absolute_uri(
            reverse('collaboration:accept_invitation', kwargs={'token': invitation.token})
        ),
        'decline_url': request.build_absolute_uri(
            reverse('collaboration:decline_invitation', kwargs={'token': invitation.token})
        )
    }
    
    subject = _('Invitation to join project: {0}').format(invitation.project.title)
    message = render_to_string('collaboration/email/invitation_email.txt', context)
    html_message = render_to_string('collaboration/email/invitation_email.html', context)
    
    send_mail(
        subject,
        message,
        'noreply@pulseconnect.org',
        [invitation.email],
        html_message=html_message,
        fail_silently=False
    )


@login_required
def accept_invitation(request, token):
    """Accept a project invitation"""
    invitation = get_object_or_404(
        ProjectInvitation, 
        token=token,
        status='pending'
    )
    
    # Check if invitation is expired
    if invitation.is_expired:
        invitation.status = 'expired'
        invitation.save()
        messages.error(request, _('This invitation has expired.'))
        return redirect('collaboration:project_list')
    
    # Check if the invitation is for the current user
    if invitation.invited_user and invitation.invited_user != request.user:
        messages.error(request, _('This invitation is for another user.'))
        return redirect('collaboration:project_list')
    
    if not invitation.invited_user and invitation.email != request.user.email:
        messages.error(request, _('This invitation is for another email address.'))
        return redirect('collaboration:project_list')
    
    # Accept the invitation
    invitation.status = 'accepted'
    invitation.responded_at = timezone.now()
    invitation.save()
    
    # Create membership
    ProjectMembership.objects.create(
        project=invitation.project,
        user=request.user,
        role=invitation.role,
        can_edit=(invitation.role in ['coordinator', 'researcher']),
        can_invite=(invitation.role == 'coordinator')
    )
    
    messages.success(request, _('You have joined the project: {0}').format(invitation.project.title))
    return redirect('collaboration:project_detail', pk=invitation.project.pk)


@login_required
def decline_invitation(request, token):
    """Decline a project invitation"""
    invitation = get_object_or_404(
        ProjectInvitation, 
        token=token,
        status='pending'
    )
    
    # Check if invitation is expired
    if invitation.is_expired:
        invitation.status = 'expired'
        invitation.save()
        messages.error(request, _('This invitation has expired.'))
        return redirect('collaboration:project_list')
    
    # Check if the invitation is for the current user
    if invitation.invited_user and invitation.invited_user != request.user:
        messages.error(request, _('This invitation is for another user.'))
        return redirect('collaboration:project_list')
    
    if not invitation.invited_user and invitation.email != request.user.email:
        messages.error(request, _('This invitation is for another email address.'))
        return redirect('collaboration:project_list')
    
    # Decline the invitation
    invitation.status = 'declined'
    invitation.responded_at = timezone.now()
    invitation.save()
    
    messages.info(request, _('You have declined the invitation to join the project.'))
    return redirect('collaboration:project_list')


@login_required
@require_POST
def cancel_invitation(request, invitation_pk):
    """Cancel a pending invitation"""
    invitation = get_object_or_404(ProjectInvitation, pk=invitation_pk, status='pending')
    project = invitation.project
    
    # Check if user can invite
    can_invite = (project.owner == request.user)
    if not can_invite:
        try:
            membership = ProjectMembership.objects.get(project=project, user=request.user)
            can_invite = membership.can_invite
        except ProjectMembership.DoesNotExist:
            can_invite = False
    
    if not can_invite:
        return HttpResponseForbidden()
    
    invitation.delete()
    messages.success(request, _('Invitation cancelled successfully!'))
    
    return redirect('collaboration:project_invitations', pk=project.pk)


@login_required
def leave_project(request, pk):
    """Leave a project"""
    project = get_object_or_404(ResearchProject, pk=pk)
    user = request.user
    
    # Cannot leave if you're the owner
    if project.owner == user:
        messages.error(request, _('As the project owner, you cannot leave the project. Transfer ownership first or delete the project.'))
        return redirect('collaboration:project_detail', pk=project.pk)
    
    # Check if user is a member
    try:
        membership = ProjectMembership.objects.get(project=project, user=user)
        membership.delete()
        
        messages.success(request, _('You have left the project successfully.'))
        return redirect('collaboration:project_list')
    except ProjectMembership.DoesNotExist:
        messages.error(request, _('You are not a member of this project.'))
        return redirect('collaboration:project_detail', pk=project.pk)


@login_required
def transfer_ownership(request, pk):
    """Transfer project ownership to another member"""
    project = get_object_or_404(ResearchProject, pk=pk)
    
    # Check if user is the owner
    if request.user != project.owner:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        new_owner_id = request.POST.get('new_owner')
        
        try:
            new_owner = User.objects.get(id=new_owner_id)
            
            # Check if new owner is a member
            if not project.members.filter(id=new_owner.id).exists():
                messages.error(request, _('The selected user is not a member of this project.'))
                return redirect('collaboration:project_detail', pk=project.pk)
            
            # Update the project owner
            project.owner = new_owner
            project.save()
            
            # Update memberships
            old_owner_membership = ProjectMembership.objects.get(project=project, user=request.user)
            new_owner_membership = ProjectMembership.objects.get(project=project, user=new_owner)
            
            # Give full permissions to new owner
            new_owner_membership.role = 'coordinator'
            new_owner_membership.can_edit = True
            new_owner_membership.can_invite = True
            new_owner_membership.save()
            
            messages.success(request, _('Project ownership transferred successfully!'))
            return redirect('collaboration:project_detail', pk=project.pk)
            
        except User.DoesNotExist:
            messages.error(request, _('User not found.'))
        except ProjectMembership.DoesNotExist:
            messages.error(request, _('Membership not found.'))
    
    # Get all members except the owner
    members = ProjectMembership.objects.filter(
        project=project
    ).exclude(user=request.user)
    
    return render(request, 'collaboration/transfer_ownership.html', {
        'project': project,
        'members': members
    })


@method_decorator(login_required, name='dispatch')
class ProjectDeleteView(UserPassesTestMixin, DeleteView):
    model = ResearchProject
    template_name = 'collaboration/project_confirm_delete.html'
    success_url = reverse_lazy('collaboration:project_list')
    
    def test_func(self):
        project = self.get_object()
        return self.request.user == project.owner
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Project deleted successfully!'))
        return super().delete(request, *args, **kwargs)