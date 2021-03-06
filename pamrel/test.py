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
import json
import datetime
import pytz

from django.test import TestCase

from pamrel.forms import PasteForm
from pamrel.models import Paste

class PasteTest(TestCase):

    def __get_id(self, url):
        return url.split("/")[-2]

    def test_raw(self):
        """ Test that raw is given correctly """
        paste = Paste(
            id=0xFFFF,
            content="print('hello!')"
        )
        paste.save()

        raw = self.client.get("/{id}/raw/".format(id=paste.pid))
        self.assertEqual(raw.status_code, 200)
        self.assertEqual(raw.content, paste.content)

    def test_meta_information(self):
        """ Tests that meta view reports the correct information """
        created = datetime.datetime(year=2013, month=1, day=2, tzinfo=pytz.UTC)
        modified = datetime.datetime(year=2014, month=2, day=3, tzinfo=pytz.UTC)
        paste = Paste(
            id=0xffff,
            content="My paste content",
            theme="unittest",
            language="Python",
            delete_at=datetime.datetime.now(pytz.UTC)+datetime.timedelta(hours=24),
            delete_on_views=72,
            created=created,
            modified=modified
        )

        paste.save()

        meta_information = self.client.get("/api/v1/{id}/meta/".format(id=paste.pid))
        meta_information = json.loads(meta_information.content)

        # Check each value
        self.assertEqual(meta_information["theme"], paste.theme)
        self.assertEqual(meta_information["created"], created.isoformat())
        self.assertEqual(meta_information["modified"], modified.isoformat())
        self.assertEqual(meta_information["deleteOnViews"], paste.delete_on_views)
        self.assertEqual(meta_information["deleteAt"], paste.delete_at.isoformat())
        self.assertEqual(meta_information["syntax"], paste.syntax)
        self.assertEqual(meta_information["numbers"], paste.numbers)
        self.assertEqual(meta_information["viewed"], paste.viewed)

    def test_viewed_incremented(self):
        """ Test that a paste view count has been incremented upon being viewed """
        p = Paste(
            id=0x1,
            content="My paste content."
        )

        p.save()

        # Check that an unviewed paste has no views on it
        self.assertEqual(p.viewed, 0)

        # View it
        self.client.get("/{id}/".format(id=p.pid))

        # Now assert it's been incremented
        p = Paste.objects.get(pk=p.pk)
        self.assertEqual(p.viewed, 1)

    def test_delete_on_date(self):
        """ Test that it will delete a paste after a set amount of time """

        # Make the paste with a delete_at which I'll never meet in this test
        paste = Paste(
            id=0xFFFF,
            content="My paste content.",
            delete_at=datetime.datetime.now(pytz.UTC)+datetime.timedelta(hours=24)
        )
        paste.save()

        # Make sure I can get the paste
        response = self.client.get("/{id}/".format(id=paste.pid))
        self.assertEqual(response.status_code, 200)

        # Now change the date to before now
        paste.delete_at = datetime.datetime.now(pytz.UTC)-datetime.timedelta(seconds=1)
        paste.save()

        # Check that we can't see it anymore
        response = self.client.get("/{id}/".format(id=paste.pid))
        self.assertEqual(response.status_code, 404)

        # Test that the paste no longer exists in the database too
        with self.assertRaises(Paste.DoesNotExist):
            Paste.objects.get(pk=paste.pk)

    def test_delete_on_views(self):
        """ Test that it will delete on <x> number of views """
        request = {
            "content": "This is the paste content",
            "delete_on_views": 3
        }

        response = self.client.post("/", request)
        self.assertEqual(response.status_code, 200)

        # Request 3 times ensuring we get a 200 response
        url = "/{id}/".format(id=self.__get_id(response.content))
        for i in range(request["delete_on_views"]):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        # Now it should produce a 404 as it should be deleted
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_paste_utf8(self):
        """ Tests that you can post UTF-8 encoded paste data """
        # Build up list of ALL utf-8 characters
        # technically I think this should be up to 2**32 as utf-8 is 4 bytes
        # the unichr barfs at anything 0x10000 or higher.
        paste = u"".join([unichr(i) for i in range(0xffff)])
        response = self.client.post("/", {
            "content": paste
        })
        self.assertEqual(response.status_code, 200)
