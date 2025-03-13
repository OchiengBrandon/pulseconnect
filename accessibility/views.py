from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import AccessibilitySetting
from .forms import AccessibilitySettingForm

@login_required
def accessibility_settings(request):
    try:
        settings = AccessibilitySetting.objects.get(user=request.user)
    except AccessibilitySetting.DoesNotExist:
        settings = AccessibilitySetting(user=request.user)
    
    if request.method == 'POST':
        form = AccessibilitySettingForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            return redirect('accessibility:settings')
    else:
        form = AccessibilitySettingForm(instance=settings)

    return render(request, 'accessibility/settings.html', {'form': form})