#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import odoorpc
import time
import datetime
from toposort import toposort, toposort_flatten

# Set the enviroment variables
DATABASE = 'python2'
SERVER = 'localhost'
PORT = '8069'
USER = 'admin'
PASSWORD = '123'

# Prepare the connection to the server
odoo = odoorpc.ODOO(SERVER, port=PORT)

# Login
odoo.login(DATABASE, USER, PASSWORD)

# Current user
user = odoo.env.user
sync_data = odoo.env['ir.model.data.sync']


def get_dependences(complete_name):
    """
    Get the dependences of one register
    """
    register = odoo.env.ref(complete_name)
    not_relational_fields = [unicode, datetime.datetime, int, float, bool]
    dependences = []
    for field in register.read()[0].keys():
        # Passa por todos los capos
        field_value = eval("register."+field)
        if field == 'res_id' and register._name == 'mail.message':
            # Case it's an chatter model, it's not ane many2many but it's important to be in order
            dependences.append(odoo.env[register.model].browse(field_value).get_xml_id().values()[0])
            continue
        if field_value and type(field_value) not in not_relational_fields:
            field_type = odoo.env['ir.model.fields'].search_read([
                ('model','=',register._name),
                ('name','=',field)
                ])[0]['ttype']
            if field_type not in ['many2one','many2many']:
                continue
            for value in field_value.get_xml_id().values():
                dependences.append(value)
    return dependences


def get_order(register_ids):
    ignore = []
    new_order = []
    count = 0
    all_ids = []
    left_ids = []
    source_ids = {}
    map_ids = {}
    for reg in register_ids:
        left_ids.append({'id': reg['id'], 'name': reg['name']})
        map_ids[reg['name']] = reg['id']
        all_ids.append(reg['name'])
    for reg in left_ids:
        if reg['id'] not in ignore:
            ignore.append(reg['id'])
            dependences = get_dependences(reg['name'])
            match_dependences = list(set(all_ids) & set(dependences))
            source_ids[reg['name']] = set(match_dependences)
            #print map_ids[reg['name']]

    #Convert xml_id to id
    all_ids = []
    print "source ids %s"%source_ids
    ordered_list = toposort_flatten(source_ids)
    print "reorder_ids %s"%ordered_list
    for xml_name in ordered_list:
        print "id: %s  %s"%(map_ids[xml_name], xml_name)
        all_ids.append(map_ids[xml_name])
    return all_ids


Order = odoo.env['ir.model.data.sync.queue']
order_ids = Order.search_read([])
ignore = []
register_ids = get_order(order_ids)
print "registers %s"%register_ids
for register in register_ids:
    sync_data.create_couch2([1], register)
