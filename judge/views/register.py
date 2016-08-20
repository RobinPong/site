# coding=utf-8
import re

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.forms import CharField, ChoiceField, ModelChoiceField, TextInput
from django.shortcuts import render
from django.utils.translation import ugettext, ugettext_lazy as _
from registration.backends.default.views import (RegistrationView as OldRegistrationView,
                                                 ActivationView as OldActivationView)
from registration.forms import RegistrationForm
from sortedm2m.forms import SortedMultipleChoiceField

from judge.models import Profile, Language, Organization, TIMEZONE
from judge.utils.subscription import Subscription, newsletter_id
from judge.widgets import Select2Widget

valid_id = re.compile(r'^\w+$')


class CustomRegistrationForm(RegistrationForm):
    username = forms.RegexField(regex=r'^\w+$', max_length=30, label=_('Username'),
                                error_messages={'invalid': _('A username must contain letters, '
                                                             'numbers, or underscores')})
    display_name = CharField(max_length=50, required=False, label=_('Real name (optional)'))
    timezone = ChoiceField(label=_('Location'), choices=TIMEZONE,
                           widget=Select2Widget(attrs={'style': 'width:100%'}))
    language = ModelChoiceField(queryset=Language.objects.all(), label=_('Preferred language'), empty_label=None,
                                widget=Select2Widget(attrs={'style': 'width:100%'}))
    organizations = SortedMultipleChoiceField(queryset=Organization.objects.filter(is_open=True),
                                              label=_('Organizations'), required=False)

    if newsletter_id is not None:
        newsletter = forms.BooleanField(label=_('Subscribe to newsletter?'), initial=True, required=False)

    def __init__(self, *args, **kwargs):
        super(CustomRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget = TextInput(attrs={'placeholder': _('john_doe')})
        self.fields['email'].widget = TextInput(attrs={'placeholder': _('john.doe@company.com')})
        self.fields['password1'].widget = TextInput(attrs={'placeholder': _('•••••••••••')})
        self.fields['password2'].widget = TextInput(attrs={'placeholder': _('•••••••••••')})

    def clean_email(self):
        if User.objects.filter(email=self.cleaned_data['email']).exists():
            raise forms.ValidationError(ugettext(u'The email address "%s" is already taken. Only one registration '
                                                 u'is allowed per address.') % self.cleaned_data['email'])
        if '@' in self.cleaned_data['email'] and \
                        self.cleaned_data['email'].split('@')[-1] in getattr(settings, 'BAD_MAIL_PROVIDERS', set()):
            raise forms.ValidationError(ugettext(u'Your email provider is not allowed due to history of abuse. '
                                                 u'Please use a reputable email provider.'))
        return self.cleaned_data['email']


class RegistrationView(OldRegistrationView):
    title = _('Registration')
    form_class = CustomRegistrationForm
    template_name = 'registration/registration_form.jade'

    def get_context_data(self, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = self.title
        tzmap = getattr(settings, 'TIMEZONE_MAP', None)
        kwargs['TIMEZONE_MAP'] = tzmap or 'http://momentjs.com/static/img/world.png'
        kwargs['TIMEZONE_BG'] = getattr(settings, 'TIMEZONE_BG', None if tzmap else '#4E7CAD')
        return super(RegistrationView, self).get_context_data(**kwargs)

    def register(self, form):
        user = super(RegistrationView, self).register(form)
        profile, _ = Profile.objects.get_or_create(user=user, defaults={
            'language': Language.get_python2()
        })

        cleaned_data = form.cleaned_data
        profile.name = cleaned_data['display_name']
        profile.timezone = cleaned_data['timezone']
        profile.language = cleaned_data['language']
        profile.organizations.add(*cleaned_data['organizations'])
        profile.save()

        if newsletter_id is not None and cleaned_data['newsletter']:
            Subscription(user=user, newsletter_id=newsletter_id, subscribed=True).save()
        return user

    def get_initial(self, *args, **kwargs):
        initial = super(RegistrationView, self).get_initial(*args, **kwargs)
        initial['timezone'] = getattr(settings, 'DEFAULT_USER_TIME_ZONE', 'America/Toronto')
        initial['language'] = Language.objects.get(key=getattr(settings, 'DEFAULT_USER_LANGUAGE', 'PY2'))
        return initial


class ActivationView(OldActivationView):
    title = _('Registration')
    template_name = 'registration/activate.jade'

    def get_context_data(self, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = self.title
        return super(ActivationView, self).get_context_data(**kwargs)


def social_auth_error(request):
    return render(request, 'generic_message.jade', {
        'title': ugettext('Authentication failure'),
        'message': request.GET.get('message')
    })
