#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import odoorpc

# Set the enviroment variables
DATABASE = 'nodoo1'
SERVER = 'localhost'
PORT = '80'
USER = 'admin'
PASSWORD = 'admin'

# Prepare the connection to the server
odoo = odoorpc.ODOO(SERVER, port=PORT)

# Login
odoo.login(DATABASE, USER, PASSWORD)

# Current user
user = odoo.env.user
sync_data = odoo.env['ir.model.data.sync'].browse(1)
hostname = sync_data.hostname
last_seq = sync_data.last_seq
sincronizador = odoo.env['ir.model.data.sync']

couch = couchdb.Server()
db = couch[sync_data.couch_database]

retry_ids = []
for changes in db.changes(
        feed='continuous', heartbeat='1000', include_docs=True,
        since=last_seq):
    # if changes['doc']['hostnamke'] != hostname:
    # changes['doc'].pop('hostnamke', None)
    print "%s - Importing %s" % (changes['seq'], changes['doc']['_id'])
    importation = sincronizador.import_doc([1], changes['doc'])
    if importation:
        sync_data.last_seq = changes['seq']
    print importation
