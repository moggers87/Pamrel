##
# Copyright (C) 2014 Jessica Tallon
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
##

import hashlib
import datetime
import json

from django import forms
from django.core import exceptions

from pamrel import models

from pygments import lexers

class PasteForm(forms.ModelForm):
	""" Form to create a paste """

	language = forms.ChoiceField(
		required=False,
                choices=(
                        ('', 'Auto Detect'),
                        ('PlainText', 'Plain Text'),
		)
	)

	json_prettify = forms.BooleanField(required=False)
	delete_at = forms.DateTimeField(required=False, input_formats=["%Y%m%dT%H:%M:%S"])

	class Meta:
		model = models.Paste
		fields = ["content", "delete_on_views", "delete_at"]

	def __init__(self, initial=None, *args, **kwargs):
		super(PasteForm, self).__init__(initial=initial, *args, **kwargs)
		# Load all the choices for the languages pygments currently supports
		languages = dict(((lexer[0], lexer[1][0]) for lexer in lexers.get_all_lexers()))
		sorted_languages = languages.keys()
		sorted_languages.sort()
		self.fields['language'].choices += ((languages[name], name) for name in sorted_languages)
		self.fields['content'].widget.attrs.update({'placeholder': '<code> ... </code>'})

	def create_id(self, attempts=0):
		""" Create a (hopefully) non-consequitive ID """
		# The best way of creating a unique ID i think would be
		# to sha1(content + posttime) and use that
		whole_id = hashlib.sha1(self.cleaned_data['content'].encode("utf-8") + datetime.datetime.now().isoformat()).hexdigest()
		for block in range(5, len(whole_id), 6):
			pid = int(whole_id[0:block], 16)
			if not models.Paste.objects.filter(pk=pid).exists():
				return pid

		if attempts >= 3:
			raise Exception("Unable to create past as ID pool is too small.")

		return self.create_id(attempts=attempts+1)

	def detect_language(self, data):
		""" Detects the language of the paste """
		try:
			lexer = lexers.guess_lexer(data)
		except Exception:
			return "PlainText"

		# for some unknown reason get_lexer_by_name(lexer.name) doesn't work >.>
		# however get_lexer_by_name(lexer.aliases[0]) does.
		return lexer.aliases[0]

	def clean(self, *args, **kwargs):
		cleaned_data = super(PasteForm, self).clean(*args, **kwargs)

		if cleaned_data.get('json_prettify', False):
			try:
				cleaned_data['content'] = json.dumps(
					json.loads(cleaned_data['content']),
					{'4': 5, '6': 7},
					sort_keys=True,
					indent=4,
					separators=(',', ': ')
				)

				cleaned_data['language'] = 'js'
			except ValueError:
				raise exceptions.ValidationError("Error parsing JSON content.")

		return cleaned_data

	def save(self, *args, **kwargs):
		obj = super(PasteForm, self).save(*args, **kwargs)

		# Sigh - there must be a better way right?
		obj.id = self.create_id()

		# Set language.
		if not self.cleaned_data.get("language", ""):
			obj.language = self.detect_language(self.cleaned_data["content"])
		else:
			obj.language = self.cleaned_data['language']

		# If we don't know the language, don't try syntax highlighting (duh!)
		if obj.language == "PlainText":
			obj.syntax = False
		else:
			obj.syntax = True

		obj.save()
		return obj
