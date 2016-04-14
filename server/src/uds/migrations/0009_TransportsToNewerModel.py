# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from uds.core.ui.UserInterface import gui
from uds.transports.RDP.RDPTransport import RDPTransport
from uds.transports.RDP.TRDPTransport import TRDPTransport

from uds.core.Environment import Environment


def unmarshalRDP(str_):
    data = str_.split('\t')
    if data[0] in ('v1', 'v2', 'v3'):
        useEmptyCreds = gui.strToBool(data[1])
        allowSmartcards = gui.strToBool(data[2])
        allowPrinters = gui.strToBool(data[3])
        allowDrives = gui.strToBool(data[4])
        allowSerials = gui.strToBool(data[5])

        if data[0] == 'v1':
            wallpaper = False
            i = 0

        if data[0] in ('v2', 'v3'):
            wallpaper = gui.strToBool(data[6])
            i = 1

        fixedName = data[6 + i]
        fixedPassword = data[7 + i]
        fixedDomain = data[8 + i]

        if data[0] == 'v3':
            withoutDomain = gui.strToBool(data[9 + i])
        else:
            withoutDomain = False

    return {
        'useEmptyCreds': useEmptyCreds,
        'allowSmartcards': allowSmartcards,
        'allowPrinters': allowPrinters,
        'allowDrives': allowDrives,
        'allowSerials': allowSerials,
        'wallpaper': wallpaper,
        'fixedName': fixedName,
        'fixedPassword': fixedPassword,
        'fixedDomain': fixedDomain,
        'withoutDomain': withoutDomain
    }


def unmarshalTRDP(str_):
    data = str_.split('\t')
    if data[0] in ('v1', 'v2', 'v3'):
        useEmptyCreds = gui.strToBool(data[1])
        allowSmartcards = gui.strToBool(data[2])
        allowPrinters = gui.strToBool(data[3])
        allowDrives = gui.strToBool(data[4])
        allowSerials = gui.strToBool(data[5])
        if data[0] == 'v1':
            wallpaper = False
            i = 0

        if data[0] in ('v2', 'v3'):
            wallpaper = gui.strToBool(data[6])
            i = 1

        fixedName = data[6 + i]
        fixedPassword = data[7 + i]
        fixedDomain = data[8 + i]
        tunnelServer = data[9 + i]
        tunnelCheckServer = data[10 + i]

        if data[0] == 'v3':
            withoutDomain = gui.strToBool(data[11 + i])
        else:
            withoutDomain = False

    return {
        'useEmptyCreds': useEmptyCreds,
        'allowSmartcards': allowSmartcards,
        'allowPrinters': allowPrinters,
        'allowDrives': allowDrives,
        'allowSerials': allowSerials,
        'wallpaper': wallpaper,
        'fixedName': fixedName,
        'fixedPassword': fixedPassword,
        'fixedDomain': fixedDomain,
        'withoutDomain': withoutDomain,
        'tunnelServer': tunnelServer,
        'tunnelCheckServer': tunnelCheckServer
    }

def transformTransports(apps, schema_editor):
    '''
    Move serialization to a better model (it's time, the mode is there since 1.1 :) )
    '''
    model = apps.get_model("uds", 'Transport')
    for t in model.objects.all():
        if t.data_type == RDPTransport.typeType:
            values = unmarshalRDP(t.data.decode(RDPTransport.CODEC))
            rdp = RDPTransport(Environment.getTempEnv(), values)
            t.data = rdp.serialize()
            t.save()

        if t.data_type == TRDPTransport.typeType:
            values = unmarshalTRDP(t.data.decode(TRDPTransport.CODEC))
            rdp = TRDPTransport(Environment.getTempEnv(), values)
            t.data = rdp.serialize()
            t.save()


def untransformTransports(apps, schema_editor):
    raise Exception('This migration can\'t be undone')


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0008_userserviceproperty'),
    ]

    operations = [
        migrations.RunPython(
            transformTransports,
            untransformTransports
        ),
    ]
