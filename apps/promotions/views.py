from django.views.generic import TemplateView, RedirectView


class HomeView(TemplateView):
    """
    This is the home page and will typically live at /
    """
    template_name = 'promotions/home.html'
