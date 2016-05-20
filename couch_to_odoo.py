#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import odoorpc

# Set the enviroment variables
DATABASE = 'python2-sync'
SERVER = 'localhost'
PORT = '8069'
USER = 'admin'
PASSWORD = '123'
couch_database = 'python2'

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
sync_data = odoo.env['ir.model.data.sync'].browse(1)
server = sync_data.server
last_seq = sync_data.last_seq
xmlid = odoo.env['ir.model.data.sync']

#print server

couch = couchdb.Server()
db = couch[couch_database]

retry_ids = []
for changes in db.changes(feed='continuous',heartbeat='1000',include_docs=True, since=last_seq):
    #print "Importing changes" % changes
    #print changes['doc']
    if changes['doc']['server'] != server:
        changes['doc'].pop('server', None)
        print "%s - Importing %s"%(changes['seq'],changes['doc']['xml_id'])
        importation =  xmlid.import_doc([1], changes['doc'])
        if importation:
            sync_data.last_seq = changes['seq']
        print importation
        #if not importation['ids']:
        #    if not changes['doc'] in retry_ids:
        #        retry_ids.append(changes['doc'])
        #for retry in retry_ids:
        #    print "Retring %s"%(retry)
        #    importation =  xmlid.import_doc([1], retry)
        #    if importation['ids']:
        #        retry_ids.pop(retry, None)
        #    print importation

