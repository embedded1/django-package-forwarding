# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse
from django.utils.translation import get_language, activate
import os, datetime

class I18nSitemap(Sitemap):
    """
    A language-specific Sitemap class. Returns URLS for items for passed
    language.
    """
    def __init__(self, language):
        self.language = language
        self.original_language = get_language()

    def get_obj_location(self, obj):
        return obj.get_absolute_url()

    def location(self, obj):
        activate(self.language)
        location = self.get_obj_location(obj)
        activate(self.original_language)
        return location


class StaticSitemap(Sitemap):
    protocol = 'https'
    priority = 0.5
    changefreq = 'monthly'
    _items = [
        'promotions:home', 'calculators:package',
        'calculators:amazon', 'contact', 'aboutus', 'pricing',
        'features', 'fees-explained', 'terms', 'chrome-ext',
        'privacy', 'referral-program', 'affiliate-program',
        {
            'folder': '',
            'name': 'chrome-ext'
        },
        {
            'folder': '',
            'name': 'customer:login'
        },
        {
            'folder': '',
            'name': 'customer:register'
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'ca',
                'country_name': 'canada'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'au',
                'country_name': 'australia'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'fr',
                'country_name': 'france'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'gb',
                'country_name': 'united-kingdom'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'ru',
                'country_name': 'russia'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'br',
                'country_name': 'brazil'
            }
        },
        {
            'folder': '',
            'name': 'forwarding-destination',
            'kwargs': {
                'country_code': 'sa',
                'country_name': 'saudi-arabia'
            }
        },
        {
            'folder': 'static:faq:control-panel',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'control-panel',
            }
        },
        {
            'folder': 'static:faq:intro',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'intro',
            }
        },
        {
            'folder': 'static:faq:package-handling',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'package-handling',
            }
        },
        {
            'folder': 'static:faq:pricing',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'pricing',
            }
        },
        {
            'folder': 'static:faq:referral-program',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'referral-program',
            }
        },
        {
            'folder': 'static:faq:shipping',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'shipping',
            }
        },
        {
            'folder': 'static:faq:tutorials',
            'name': 'faq',
            'kwargs': {
                'active_tab': 'tutorials',
            }
        },
    ]
    _items_lastmod = {}

    def __init__(self):
        self._initialize()

    def _initialize(self):
        for item in self._items:
            self._items_lastmod[item['name'] if isinstance(item, dict) else item] = self._get_modification_date(item)

    def _get_modification_date(self, item):
        if not isinstance(item, dict):
            tokens = item.rsplit(':', 1)
            try:
                template_folder = tokens[0]
                template_name = tokens[1]
            except IndexError:
                template_folder = 'static'
                template_name = tokens[0]

            template_name += r'.html'
            template_folder = template_folder.replace(':', '/')
            template_path = self._get_template_path(template_folder, template_name)
        else:
            return self._get_modification_date(item['folder'])
        if template_path:
            mtime = os.path.getmtime(template_path)
            return datetime.datetime.fromtimestamp(mtime)
        return None

    def _get_template_path(self, template_folder, template_name):
        for template_dir in settings.TEMPLATE_DIRS:
            path = os.path.join(template_dir, template_folder, template_name)
            if os.path.exists(path):
                return path
        return None

    def items(self):
        return self._items

    def location(self, obj):
        if isinstance(obj, dict):
            kwargs = obj.get('kwargs')
            if kwargs:
                return reverse(obj['name'], kwargs=kwargs)
            return reverse(obj['name'])
        return reverse(obj)

    def lastmod(self, obj):
        if isinstance(obj, dict):
             return self._items_lastmod[obj['name']]
        return self._items_lastmod[obj]


base_sitemaps = {
    'static': StaticSitemap,
}

# Construct the sitemaps for every language
#base_sitemaps = {}
#for language, __ in settings.LANGUAGES:
#    for name, sitemap_class in language_neutral_sitemaps.items():
#        base_sitemaps['{0}-{1}'.format(name, language)] = sitemap_class(language)