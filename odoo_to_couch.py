#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import odoorpc
import time
import datetime

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


def get_order(register_ids):
    ignore = []
    new_order = []
    count = 0
    all_ids = []
    left_ids = []
    for reg in register_ids:
        left_ids.append({'id': reg['id'], 'name': reg['name']})
        all_ids.append(reg['id'])

    for reg in left_ids:
        

        if reg['id'] not in ignore:
            print "passing by %s %s"%(reg['id'], reg['name'])
            ignore.append(reg['id'])

            register = odoo.env.ref(reg['name'])
            not_relational_fields = [unicode, datetime.datetime, int, float, bool]
            for field in register.read()[0].keys():
                # Passa por todos los capos
                field_value = eval("register."+field)
                if field_value and type(field_value) not in not_relational_fields:
                    #print register._name
                    field_type = odoo.env['ir.model.fields'].search_read([
                        ('model','=',register._name),
                        ('name','=',field)
                        ])[0]['ttype']
                    #field_register = odoo.env['']
                    if field_type != 'many2one':
                        continue
                    #passa solo por los campos relevantes
                    register_index = all_ids.index(reg['id'])
                    dependence = Order.search([('name','in',field_value.get_xml_id().values())])
                    if len(dependence)==0:
                        continue
                    print "the field %s depends on %s %s"%(field, dependence[0], field_value.get_xml_id().values())
                    dependence_index = all_ids.index(dependence[0])
                    if register_index < dependence_index:
                        all_ids.pop(register_index)
                        all_ids.insert(dependence_index+1, reg['id'])
                        ignore.append(dependence[0])
                        print "register_index %s dependence %s"%(register_index, dependence_index)

    return all_ids


Order = odoo.env['ir.model.data.sync.queue']
order_ids = Order.search_read([])
ignore = []
register_ids = get_order(order_ids)
print register_ids
for register in register_ids:
    sync_data.create_couch2([1], register)


