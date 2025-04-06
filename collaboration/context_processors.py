from collaboration.models import ProjectInvitation
from django.db.models import Q


def user_invitations(request):
    """Add user invitations count to context"""
    if request.user.is_authenticated:
        invitations_count = ProjectInvitation.objects.filter(
            (Q(email=request.user.email) | Q(invited_user=request.user)) &
            Q(status='pending')
        ).count()
        return {'user_invitations_count': invitations_count}
    return {'user_invitations_count': 0}