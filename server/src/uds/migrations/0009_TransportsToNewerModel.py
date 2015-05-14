# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from uds.core.ui.UserInterface import gui
from uds.transports.RDP.RDPTransport import RDPTransport
from uds.transports.RDP.TRDPTransport import TRDPTransport
try:
    from uds.transports.RGS import RGSTransport  # @UnresolvedImport, pylint: disable=import-error, no-name-in-module
    from uds.transports.RGS import TRGSTransport  # @UnresolvedImport, pylint: disable=import-error, no-name-in-module
except Exception:
    from uds.transports.RGS_enterprise import RGSTransport  # @UnresolvedImport @Reimport, pylint: disable=import-error, no-name-in-module
    from uds.transports.RGS_enterprise import TRGSTransport  # @UnresolvedImport @Reimport, pylint: disable=import-error, no-name-in-module

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


def unmarshalRGS(data):
    data = data.split('\t')
    if data[0] == 'v1':
        useEmptyCreds = gui.strToBool(data[1])
        fixedName = data[2]
        fixedPassword = data[3]
        fixedDomain = data[4]
        imageQuality = data[5]
        adjustableQuality = gui.strToBool(data[6])
        minAdjustableQuality = data[7]
        minAdjustableRate = data[8]
        matchLocalDisplay = gui.strToBool(data[9])
        redirectUSB = gui.strToBool(data[10])
        redirectAudio = gui.strToBool(data[11])
        redirectMIC = gui.strToBool(data[12])

    return {
        'fixedName': fixedName,
        'fixedPassword': fixedPassword,
        'fixedDomain': fixedDomain,
        'useEmptyCreds': useEmptyCreds,
        'imageQuality': imageQuality,
        'adjustableQuality': adjustableQuality,
        'minAdjustableQuality': minAdjustableQuality,
        'minAdjustableRate': minAdjustableRate,
        'matchLocalDisplay': matchLocalDisplay,
        'redirectUSB': redirectUSB,
        'redirectAudio': redirectAudio,
        'redirectMIC': redirectMIC
    }


def unmarshalTRGS(data):
    data = data.split('\t')
    if data[0] == 'v1':
        useEmptyCreds = gui.strToBool(data[1])
        fixedName = data[2]
        fixedPassword = data[3]
        fixedDomain = data[4]
        imageQuality = int(data[5])
        adjustableQuality = gui.strToBool(data[6])
        minAdjustableQuality = int(data[7])
        minAdjustableRate = int(data[8])
        matchLocalDisplay = gui.strToBool(data[9])
        redirectUSB = gui.strToBool(data[10])
        redirectAudio = gui.strToBool(data[11])
        redirectMIC = gui.strToBool(data[12])
        tunnelServer = data[13]
        tunnelCheckServer = data[14]

    return {
        'fixedName': fixedName,
        'fixedPassword': fixedPassword,
        'fixedDomain': fixedDomain,
        'useEmptyCreds': useEmptyCreds,
        'imageQuality': imageQuality,
        'adjustableQuality': adjustableQuality,
        'minAdjustableQuality': minAdjustableQuality,
        'minAdjustableRate': minAdjustableRate,
        'matchLocalDisplay': matchLocalDisplay,
        'redirectUSB': redirectUSB,
        'redirectAudio': redirectAudio,
        'redirectMIC': redirectMIC,
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

        if t.data_type == RGSTransport.typeType:
            values = unmarshalRGS(t.data.decode(RGSTransport.CODEC))
            rgs = RGSTransport(Environment.getTempEnv(), values)
            t.data = rgs.serialize()
            t.save()

        if t.data_type == TRGSTransport.typeType:
            values = unmarshalTRGS(t.data.decode(TRGSTransport.CODEC))
            rgs = TRGSTransport(Environment.getTempEnv(), values)
            t.data = rgs.serialize()
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
