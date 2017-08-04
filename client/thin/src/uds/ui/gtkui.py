# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

import re

import pygtk
pygtk.require('2.0')
import gtk
import gobject

LINE_LEN = 65

class Dialog():
    def __init__(self, title, message, timeout=-1, withCancel=True):
        self.title = title
        self.message = message
        self.timeout = timeout
        self.withCancel = withCancel

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_position(gtk.WIN_POS_CENTER)
        # self.window.set_size_request(320, 200)
        self.window.set_title(self.title)
        self.create_widgets()
        self.connect_signals()
        self.window.show_all()

        self.window.connect("destroy", self.destroy)

        # Setup "auto OK" timer
        if timeout != -1:
            self.timerId = gobject.timeout_add(self.timeout * 1000, self.callback_timer)
        else:
            self.timerId = -1

        self.result = False

        gtk.main()

    @property
    def adapted_message(self):
        msg = ''
        for l in re.sub(r'<p[^>]*>', '', self.message).replace('</p>', '\n').split('\n'):
            words = []
            length = 0
            for word in l.split(' '):
                if length + len(word) >= LINE_LEN:
                    msg += ' '.join(words) + '\n'
                    words = []
                    length = 0
                length += len(word) + 1
                words.append(word)
            msg += ' '.join(words) + '\n'
        return msg

    def create_widgets(self):
        self.vbox = gtk.VBox(spacing=10)
        self.vbox.set_size_request(490, -1)

        self.messageLabel = gtk.Label()
        # Fix message markup
        # self.message = re.sub(r'<p[^>]*>', '<span font_weight="bold">', self.message).replace('</p>', '</span>\n' )

        # Set as simple markup
        self.messageLabel.set_markup('\n' + self.adapted_message + '\n')
        self.messageLabel.set_alignment(xalign=0.5, yalign=1)

        self.hbox = gtk.HBox(spacing=10)
        self.button_ok = gtk.Button("OK")
        self.hbox.pack_start(self.button_ok)

        if self.withCancel:
            self.button_cancel = gtk.Button("Cancel")
            self.hbox.pack_start(self.button_cancel)

        self.vbox.pack_start(self.messageLabel)
        self.vbox.pack_start(self.hbox)

        self.window.add(self.vbox)

    def connect_signals(self):
        self.button_ok.connect("clicked", self.callback_ok)
        if self.withCancel:
            self.button_cancel.connect("clicked", self.callback_cancel)

    def destroy(self, widget, data=None):
        self.setResult(False)

    def setResult(self, val):
        if self.timerId != -1:
            gobject.source_remove(self.timerId)
            self.timerId = -1

        self.result = val
        self.window.hide()
        gtk.main_quit()


    def callback_ok(self, widget, callback_data=None):
        self.setResult(True)

    def callback_cancel(self, widget, callback_data=None):
        self.setResult(False)

    def callback_timer(self):
        self.setResult(True)

def message(title, message):
    Dialog(title, message, withCancel=False)

def question(title, message):
    dlg = Dialog(title, message, timeout=30, withCancel=True)
    return dlg.result
