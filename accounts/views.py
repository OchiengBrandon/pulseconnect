from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse

from .models import User, UserVerification, InstitutionProfile, Follow
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, 
    UserProfileForm, InstitutionProfileForm, AccessibilitySettingsForm
)

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:verification_sent')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.instance
        
        # Create verification token
        token = get_random_string(64)
        expiry = timezone.now() + timezone.timedelta(days=3)
        UserVerification.objects.create(
            user=user,
            verification_token=token,
            token_expiry=expiry
        )
        
        # Send verification email
        verification_url = self.request.build_absolute_uri(
            reverse_lazy('accounts:verify', kwargs={'token': token})
        )
        context = {
            'user': user,
            'verification_url': verification_url,
        }
        email_subject = _('Verify your PulseConnect account')
        email_body = render_to_string('accounts/email/verification_email.html', context)
        
        send_mail(
            email_subject,
            email_body,
            'noreply@pulseconnect.org',
            [user.email],
            html_message=email_body,
            fail_silently=False,
        )
        
        # If user is an institution, create institution profile
        if user.user_type == 'institution':
            InstitutionProfile.objects.create(user=user)
        
        # Log the user in
        login(self.request, user)
        
        return response


class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'

@login_required
def follow_user(request, username):
    target_user = get_object_or_404(User, username=username)
    
    if request.method == 'POST':
        if request.user.is_following(target_user):
            request.user.unfollow(target_user)
            is_following = False
        else:
            request.user.follow(target_user)
            is_following = True
        
        return JsonResponse({'is_following': is_following})

    return JsonResponse({'error': 'Invalid request'}, status=400)

def verify_email(request, token):
    verification = get_object_or_404(
        UserVerification, 
        verification_token=token,
        token_expiry__gt=timezone.now()
    )
    
    verification.is_verified = True
    verification.verification_token = None
    verification.token_expiry = None
    verification.save()
    
    messages.success(request, _('Your account has been successfully verified!'))
    return redirect('accounts:profile', username=verification.user.username)


def verification_sent(request):
    return render(request, 'accounts/email/verification_sent.html')

@login_required
def resend_verification(request):
    user = request.user
    verification = get_object_or_404(UserVerification, user=user)

    # Check if the user is already verified
    if verification.is_verified:
        messages.info(request, _('Your account is already verified.'))
        return redirect('accounts:profile', username=user.username)

    # Generate a new token and expiry
    token = get_random_string(64)
    expiry = timezone.now() + timezone.timedelta(days=3)
    verification.verification_token = token
    verification.token_expiry = expiry
    verification.save()

    # Send the verification email again
    verification_url = request.build_absolute_uri(
        reverse_lazy('accounts:verify', kwargs={'token': token})
    )
    context = {
        'user': user,
        'verification_url': verification_url,
    }
    email_subject = _('Verify your PulseConnect account')
    email_body = render_to_string('accounts/email/verification_email.html', context)

    send_mail(
        email_subject,
        email_body,
        'noreply@pulseconnect.org',
        [user.email],
        html_message=email_body,
        fail_silently=False,
    )

    messages.success(request, _('A new verification email has been sent to your email address.'))
    return redirect('accounts:profile', username=user.username)


class ProfileDetailView(DetailView):
    model = User
    template_name = 'accounts/profile_detail.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        
        # Add institution profile if applicable
        if user.user_type == 'institution':
            context['institution_profile'] = InstitutionProfile.objects.filter(user=user).first()
        
        # Add user stats
        from polls.models import Poll, PollResponse
        from community.models import Discussion, Comment
        
        context['polls_created'] = Poll.objects.filter(creator=user).count()
        context['polls_participated'] = PollResponse.objects.filter(user=user).count()
        context['discussions_created'] = Discussion.objects.filter(creator=user).count()
        context['comments_made'] = Comment.objects.filter(user=user).count()
        
        # Get gamification data
        from gamification.models import UserPoints, Badge
        
        context['user_points'] = UserPoints.objects.filter(user=user).first()
        context['badges'] = Badge.objects.filter(users=user)
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'accounts/profile_edit.html'
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add institution profile form if applicable
        if self.request.user.user_type == 'institution':
            institution_profile = InstitutionProfile.objects.filter(user=self.request.user).first()
            if self.request.method == 'POST':
                context['institution_form'] = InstitutionProfileForm(
                    self.request.POST, 
                    self.request.FILES,
                    instance=institution_profile
                )
            else:
                context['institution_form'] = InstitutionProfileForm(instance=institution_profile)
        
        # Add accessibility form
        if self.request.method == 'POST':
            context['accessibility_form'] = AccessibilitySettingsForm(
                self.request.POST, 
                instance=self.request.user
            )
        else:
            context['accessibility_form'] = AccessibilitySettingsForm(instance=self.request.user)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        
        # Save institution form if applicable
        if self.request.user.user_type == 'institution' and 'institution_form' in context:
            institution_form = context['institution_form']
            if institution_form.is_valid():
                institution_form.save()
        
        # Save accessibility form
        accessibility_form = context['accessibility_form']
        if accessibility_form.is_valid():
            accessibility_form.save()
        
        messages.success(self.request, _('Your profile has been updated successfully!'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounts:profile', kwargs={'username': self.request.user.username})


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')


@login_required
def password_change_done(request):
    messages.success(request, _('Your password has been changed successfully!'))
    return redirect('accounts:profile', username=request.user.username)


class ResearcherDirectoryView(ListView):
    model = User
    template_name = 'accounts/researcher_directory.html'
    context_object_name = 'researchers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.filter(user_type='researcher', public_profile=True)
        
        # Apply filters if provided
        field = self.request.GET.get('field', '')
        if field:
            queryset = queryset.filter(field_of_study__icontains=field)
        
        institution = self.request.GET.get('institution', '')
        if institution:
            queryset = queryset.filter(institution__icontains=institution)
        
        return queryset


class InstitutionDirectoryView(ListView):
    model = InstitutionProfile
    template_name = 'accounts/institution_directory.html'
    context_object_name = 'institutions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = InstitutionProfile.objects.filter(user__public_profile=True)
        
        # Apply filters if provided
        inst_type = self.request.GET.get('type', '')
        if inst_type:
            queryset = queryset.filter(institution_type=inst_type)
        
        return queryset


@login_required
def toggle_accessibility_setting(request):
    if request.method == 'POST' and request.is_ajax():
        setting = request.POST.get('setting')
        value = request.POST.get('value') == 'true'
        
        if setting in ('high_contrast', 'large_text'):
            setattr(request.user, setting, value)
            request.user.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)