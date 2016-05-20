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
#print(user.name)            # name of the user connected
#print(user.company_id.name) # the name of its company


# Simple 'raw' query
#user_data = odoo.execute('res.users', 'read', [user.id])
#print(user_data)

# Use all methods of a model
'''if 'sale.order' in odoo.env:
    Order = odoo.env['sale.order']
    order_ids = Order.search([])
    for order in Order.browse(order_ids):
        print(order.name)
        products = [line.product_id.name for line in order.order_line]
        print(products)

# Update data through a record
user.name = "Brian Jones"

'''
sync_data = odoo.env['ir.model.data.sync']
'''server = sync_data.server
last_seq = sync_data.last_seq
xmlid = odoo.env['ir.model.data.sync']'''

#print server

#couch = couchdb.Server()
#db = couch['python']

def get_order(register_ids):
    ignore = []
    new_order = []
    count = 0
    #print "register_ids %s"%register_ids
    all_ids = []
    left_ids = []
    for reg in register_ids:
        left_ids.append({'id': reg['id'], 'name': reg['name']})
        all_ids.append(reg['id'])

    #print left_ids

    for reg in left_ids:
        print "reg %s %s"%(reg['id'], reg['name'])

        if reg['id'] not in ignore:

            #new_order.append(reg['id'])
            #print "append %s %s"%(reg['id'], ignore)
            ignore.append(reg['id'])

            register = odoo.env.ref(reg['name'])
            not_relational_fields = [unicode, datetime.datetime, int, float, bool]
            for field in register.read()[0].keys():
                # Passa por todos los capos
                field_value = eval("register."+field)
                if field_value and type(field_value) not in not_relational_fields:
                    if len(field_value) != 1:
                        continue
                    #passa solo por los campos relevantes
                    register_index = all_ids.index(reg['id'])
                    dependence = Order.search([('name','in',field_value.get_xml_id().values())])
                    if len(dependence)==0:
                        continue
                    print "passei %s"%dependence[0]
                    dependence_index = all_ids.index(dependence[0])
                    if register_index > dependence_index:
                        all_ids.pop(register_index)
                        all_ids.insert(dependence_index, reg['id'])
                        
                        #ignore.append(dependence[0])
                        print "register_index %s dependence %s"%(register_index, dependence_index)

    return all_ids


Order = odoo.env['ir.model.data.sync.queue']
order_ids = Order.search_read([])
ignore = []
register_ids = get_order(order_ids)
print register_ids
for register in register_ids:
    sync_data.create_couch2([1], register)


