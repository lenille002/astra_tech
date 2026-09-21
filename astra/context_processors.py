from .models import NotificationPlateforme

def notifications_processor(request):
    notifications = NotificationPlateforme.objects.filter(
        lu=False
    ).order_by('-date_creation', '-id')

    return {
        'notifications_non_lues': notifications,
        'nombre_notifications': notifications.count()
    }