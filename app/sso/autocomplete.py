from dal import autocomplete

from .models import User


class UserAutcomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # only admin should ever be using this autocomplete widget
        if self.request.user and self.request.user.is_superuser:
            qs = User.objects.all().order_by('username')
            if self.q:
                qs = qs.filter(usernamename__istartswith=self.q)

            return qs
        else:
            return User.objects.none()
