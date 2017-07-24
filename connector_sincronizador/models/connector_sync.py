# -*- coding: utf-8 -*-
from openerp import models, fields, api
import couchdb
# import itertools
# import time
from toposort import toposort_flatten
import logging

_logger = logging.getLogger(__name__)


class IrModelDataSync(models.Model):
    _name = 'ir.model.data.sync'

    hostname = fields.Char(
        string="Host Name",
        )
    couchdb_server = fields.Char(
        string="Couchdb Server",
        default="localhost",
        )
    couchdb_port = fields.Integer(
        string="Couchdb port",
        default="5984",
        )
    couchdb_username = fields.Char(
        string="Couchdb Username",
        default="",
        )
    couchdb_password = fields.Char(
        string="Couchdb Password",
        default="",
        )
    couchdb_database = fields.Char(
        string="CouchDB Database",
        )
    last_seq = fields.Char(
        string="Last Sequence",
        )

    def translate_sync(self, register):
        vals = eval(register.vals)
        result = {}
        dependences = []
        for key, val in vals.iteritems():
            if type(val) == dict:
                if val['type'] == 'many2one':
                        external_ids = self.env['ir.model.data'].search([
                            ('model', '=', val['relation']),
                            ('res_id', '=', val['value'])
                            ], limit=1).complete_name or ""
                        val['value'] = external_ids
                        dependences.append(external_ids)
                elif val['type'] == 'many2many':
                    external_ids = []
                    for value in val['value']:
                        external_id = self.env['ir.model.data'].search([
                            ('model', '=', val['relation']),
                            ('res_id', '=', value)
                            ], limit=1).complete_name
                        external_ids.append(external_id)
                        dependences.append(external_id)
                    val['value'] = external_ids
                elif val['type'] == 'one2many':
                    continue
            if vals['odoo_model'] == 'mail.message':
                result['res_id'] = self.env[vals['model']].browse(
                    vals['res_id']).get_xml_id().values()[0]
                dependences.append(result['res_id'])

            if vals['odoo_model'] == 'mail.followers':
                result['res_id'] = self.env[vals['res_model']].browse(
                    vals['res_id']).get_xml_id().values()[0]
                dependences.append(result['res_id'])
            result[key] = val
        return result, dependences

    @api.multi
    def get_data_continuos(self):
        sync_data = self.env.ref('connector_sincronizador.config')
        last_seq = sync_data.last_seq
        user = sync_data.couchdb_user
        password = sync_data.couchdb_password
        sincronizador = self.env['ir.model.data.sync']

        url = "http://%s:%s" % (self.couchdb_server, self.couchdb_port)
        couch = couchdb.Server(url=url)
        couch.resource.credentials = (user, password)
        try:
            db = couch[sync_data.couchdb_database]
        except:
            db = couch.create(sync_data.couchdb_database)

        for changes in db.changes(
                feed='continuous', heartbeat='1000', include_docs=True,
                since=last_seq):
            # if changes['doc']['hostname'] != hostname:
            # changes['doc'].pop('hostname', None)
            print "%s - Importing %s" % (changes['seq'], changes['doc']['_id'])
            importation = sincronizador.import_doc(changes['doc'])
            if importation:
                sync_data.last_seq = changes['seq']
            print importation
            self.env.cr.commit()

    @api.multi
    def set_sequence(self):
        sequence = 0
        dependences = {}
        names = []
        source_ids = {}
        for change in self.env['ir.model.data.sync.queue'].search([]):
            data_translated = self.translate_sync(change)
            change.vals = data_translated[0]
            dependences[change.name] = data_translated[1]
            names.append(change.name)
        for name in names:
            match_dependences = list(set(names) & set(dependences[name]))
            source_ids[name] = set(match_dependences)
        ordered_list = toposort_flatten(source_ids)
        for name in ordered_list:
            for queue in self.env['ir.model.data.sync.queue'].search([
                    ('name', '=', name)]):
                queue.sequence = sequence
                sequence += 1

    @api.multi
    def send_changes_to_couch(self):
        self.set_sequence()
        for change in self.env['ir.model.data.sync.queue'].search(
                [], order='sequence'):
            print "sequence: %s name %s" % (change.sequence, change.name)
            change.send_to_couch()
        return True

    @api.model
    def create_couch(self, xmlid):
        url = "http://%s:%s" % (self.couchdb_server, self.couchdb_port)
        couch = couchdb.Server(url=url)
        sync_data = self.env.ref('connector_sincronizador.config')
        user = sync_data.couchdb_user
        password = sync_data.couchdb_password
        couch.resource.credentials = (user, password)
        try:
            db = couch[self.couchdb_database]
        except:
            db = couch.create(self.couchdb_database)

        if xmlid.res_id == 0:
            return
        local_record = self.env[xmlid.model].search([
            ('id', '=', xmlid.res_id),
            ])
        doc = xmlid._id and db.get(xmlid._id) \
            or {'xml_id': xmlid.complete_name}

        print "create_couch(%s)" % xmlid.complete_name

        # Create a document with all fields
        dont_sync_fields = ['__last_update', 'id']
        field_list = self.env['ir.model.fields'].search([
            ('model_id', '=', xmlid.model),
            ('name', 'not in', dont_sync_fields)
        ])

        formated_fields = self.format_fields(local_record, xmlid, field_list)
        doc = dict(doc.items() + formated_fields.items())

        if xmlid.model == 'mail.message':
            doc['res_xmlid'] = self.env['ir.model.data'].search([
                ('model', '=', doc['model']),
                ('res_id', '=', doc['res_id'])
                ]).complete_name
        doc['odoo_model'] = xmlid.model
        doc['hostname'] = self.env['ir.model.data.sync'].search(
            [], limit=1).hostname
        db.save(doc)
        if not xmlid._id:
            xmlid._id = doc['_id']
        xmlid.synchronized = True
        return True

    @api.model
    def write_couch(self, xmlid, vals):
        url = "http://%s:%s" % (self.couchdb_server, self.couchdb_port)
        couch = couchdb.Server(url=url)
        sync_data = self.env.ref('connector_sincronizador.config')
        user = sync_data.couchdb_user
        password = sync_data.couchdb_password
        couch.resource.credentials = (user, password)
        try:
            db = couch[self.couchdb_database]
        except:
            db = couch.create(self.couchdb_database)

        if xmlid.res_id == 0:
            return
        local_record = self.env[xmlid.model].search([
            ('id', '=', xmlid.res_id),
            ])
        doc = xmlid._id and db.get(xmlid._id) \
            or {'xml_id': xmlid.complete_name}

        print "write_couch(%s, %s)" % (xmlid.complete_name, vals)

        # Avoid some fields in couch
        dont_sync_fields = ['__last_update', 'id']
        field_list = []
        for field in vals.keys():
            if field in dont_sync_fields:
                field_list.pop(field, None)
            else:
                field_obj = self.env['ir.model.fields'].search([
                    ('model', '=', xmlid.model),
                    ('name', '=', field),
                    ])
                field_list.append(field_obj)

        formated_fields = self.format_fields(local_record, xmlid, field_list)
        doc = dict(doc.items() + formated_fields.items())

        if xmlid.model == 'mail.message':
            # Add the res_xmlid field to get the remote res_id correctly
            doc['res_xmlid'] = self.env['ir.model.data'].search([
                ('model', '=', doc['model']),
                ('res_id', '=', doc['res_id'])
                ]).complete_name

        doc['odoo_model'] = xmlid.model
        doc['hostname'] = self.env['ir.model.data.sync'].search(
            [], limit=1).hostname
        db.save(doc)
        if not xmlid._id:
            xmlid._id = doc['_id']
        xmlid.synchronized = True

        return True

    @api.model
    def unlink_couch(self, xmlid, vals):
        url = "http://%s:%s" % (self.couchdb_server, self.couchdb_port)
        couch = couchdb.Server(url=url)
        sync_data = self.env.ref('connector_sincronizador.config')
        user = sync_data.couchdb_user
        password = sync_data.couchdb_password
        couch.resource.credentials = (user, password)
        try:
            db = couch[self.couchdb_database]
        except:
            db = couch.create(self.couchdb_database)
        if xmlid.unlinked:
            if '_id' in doc:
                # if this already exist in couchdb, mark it to as unlinked
                doc['unlinked'] = True
                db.save(doc)
                print "delete %s" % xmlid.complete_name
        return True

    def create_xml_id(self, model, res_id):
        """ Return a valid xml_id for the record ``self``. """
        ir_model_data = self.env['ir.model.data']
        exiting_external_id = ir_model_data.search([
            ('model', '=', model),
            ('res_id', '=', res_id),
            ], limit=1)
        if exiting_external_id:
            return exiting_external_id.complete_name
        hostname = self.env['ir.model.data.sync'].browse(1).hostname
        postfix = 0
        name = '%s_%s' % (model.replace('.', '_'), res_id)

        while ir_model_data.search([
            ('module', '=', hostname),
            ('name', '=', name),
                ]):
            postfix += 1
            name = '%s_%s_%s' % (model, res_id, postfix)
        ir_model_data.create({
            'model': model,
            'res_id': res_id,
            'module': hostname,
            'name': name,
        })
        return hostname + '.' + name

    @api.multi
    def create_xmlid_for_everything(self):
        """
        Create XMLID for every register in every model
        """

        dont_sync_models = [
            'ir.model.data',
            'ir.model.data.sync',
            'ruc.list',
            'ir.attachments',
            ]

        for model in self.env['ir.model'].search([
                ('osv_memory', '!=', True),
                ('model', 'not in', dont_sync_models),
                ('sincronizable', '=', True),
                ]):
            if not self.env['ir.model.fields'].search([
                    ('model_id', '=', model.id),
                    ('name', '=', 'write_date')
                    ]):
                continue
            registers = self.env[model.model].search([])
            for register in registers:
                # the register already have xml id
                if self.env['ir.model.data'].search([
                        ('model', '=', model.model),
                        ('res_id', '=', register.id)
                        ]):
                    continue
                xml_id = self.create_xml_id(model.model, register.id)
                print "Creating external id %s" % xml_id
        return True

    @api.multi
    def send_all_to_couch(self):
        """
        All register have to have external_id
        """
        print "Preparing all data"
        url = "http://%s:%s" % (self.couchdb_server, self.couchdb_port)
        couch = couchdb.Server(url=url)
        sync_data = self.env.ref('connector_sincronizador.config')
        user = sync_data.couchdb_user
        password = sync_data.couchdb_password
        couch.resource.credentials = (user, password)
        try:
            db = couch[self.couchdb_database]
        except:
            db = couch.create(self.couchdb_database)
        dont_sync_models = [
            'ir.model.data',
            'ir.model.data.sync',
            'ir.model.data.sync.queue',
            'ruc.list', 'ir.attachments',
            ]
        all_models = self.env['ir.model'].search([
            ('osv_memory', '=', False),
            ('model', 'not in', dont_sync_models),
            ('sincronizable', '=', True),
            ])
        unused_fields = ['id', '__last_update', 'global']

        for model in all_models:
            if not self.env['ir.model.fields'].search([
                    ('name', '=', 'create_uid'),
                    ('model_id', '=', model.model)
                    ]):
                continue
            all_records = self.env[model.model].search([])
            for record in all_records:
                all_fields = record._fields
                external_id = record.get_external_id().values()[0]
                all_values = db.get(external_id) \
                    or {'_id': external_id, 'odoo_model': model.model}
                # tmp_doc = all_values.copy()

                for field in all_fields:
                    if field in unused_fields or not eval('record.'+field):
                        continue
                    if all_fields[field].type == 'many2one':
                        field_external_id = eval(
                            'record.'+field).get_external_id().values()[0]
                        all_values[field+'/id'] = field_external_id
                    elif all_fields[field].type == 'one2many':
                        continue
                    elif all_fields[field].type == 'many2many':
                        field_external_ids = ""
                        for field_external_id in eval(
                                'record.'+field).get_external_id().values():
                            field_external_ids += field_external_id+","
                        all_values[field+'/id'] = field_external_ids[:-1]
                    elif all_fields[field].type == 'reference':
                        field_register = eval('record.'+field)
                        reference = {
                            'type': 'reference',
                            'relation': field_register._name,
                            'external_id':
                                field_register.get_external_id().values()[0]
                            }
                        all_values[field] = reference
                        print reference
                    else:
                        all_values[field] = eval('record.'+field)
                # if tmp_doc != all_values.copy():
                print 'Sending document %s' % all_values['_id']
                db.save(all_values)
        _logger.warning("It's done")
        return True

    @api.multi
    def first_time(self):
        self.create_xmlid_for_everything()
        self.send_all_to_couch()
        return True

    @api.multi
    def import_doc(self, doc):
        print "doc %s" % doc
        if doc['odoo_model'] == 'im_chat.message':
            from_uid = self.env.ref(doc['from_id']['id']).id
            uuid = self.env.ref(doc['to_id']['id']).uuid
            message_type = doc['type']
            message_content = doc['message']
            self.env['im_chat.message'].with_context({
                'synchronized': True,
                }).post(from_uid, uuid, message_type, message_content)

        else:

            reserved_fields = ['_rev', 'new_password']
            vals = {}
            exceptions = [{
                'model': 'stock.move',
                'field': 'product_qty'
            }]

            for key in doc:
                ignore_field = False
                # Here we managed some wear exceptions
                for exception in exceptions:
                    if doc['odoo_model'] == exception['model'] \
                            and key == exception['field']:
                        ignore_field = True
                        continue
                if ignore_field:
                    continue

                value = doc[key]
                if key in reserved_fields:
                    continue
                if type(value) is dict:
                    if 'type' in value and value['type'] == 'reference':
                        registro = self.env.ref(value['external_id'])
                        vals[key] = "%s,%s" % (value['relation'], registro.id)
                        continue

                if key == '_id':
                    vals['id'] = value
                elif key == 'odoo_model':
                    model = value
                else:
                    if type(value) == bool and value is True:
                        vals[key] = str(value)
                    elif value is False:
                        vals.pop(key, None)
                    else:
                        vals[key] = value

            # correct the local value for the chatter
            if model == 'mail.message':
                vals['res_id'] = self.env.ref(doc['res_xmlid']).id
                vals.pop('res_xmlid', None)
            print "vals %s" % vals
            res = self.env[model].with_context({
                'synchronized': True,
                'tracking_disable': True,
                'mail_create_nosubscribe': True,
                }).load(vals.keys(), [vals.values()])
        return res

    @api.model
    def format_fields(self, local_record, xmlid, field_list):
        doc = {}
        for field in field_list:
            # This comparation is usefull to make the process faster and
            #  without strange warnings and errors
            if field.ttype == 'many2one':
                field_xmlid = self.env['ir.model.data'].search([
                    ('model', '=', field.relation),
                    ('res_id', '=', eval("local_record."+field.name+".id"))
                    ], limit=1)

                # Avoid fields pointing to him self
                if field_xmlid.complete_name == xmlid.complete_name:
                        continue
                value = {
                    'type': field.ttype,
                    'relation': field.relation,
                    'id': field_xmlid.complete_name
                    }
            elif field.ttype == 'one2many':
                # This a problem caused becouse the line is created before the
                # order
                many_ids = []
                one2many_ids = eval("local_record."+field.name)
                if len(one2many_ids.ids) == 0 \
                        or one2many_ids._name == xmlid.model:
                    # print "continuing %s %s"%(field.name, one2many_ids)
                    continue
                # print "one2many_ids %s"%eval("local_record."+field.name)
                for one_id in eval("local_record."+field.name):
                    field_xmlid = self.env['ir.model.data'].search([
                        ('model', '=', field.relation),
                        ('res_id', '=', one_id.id),
                        ], limit=1)
                    many_ids.append(field_xmlid.complete_name)
                value = {
                    'type': field.ttype,
                    'relation': field.relation,
                    'ids': many_ids
                    }
            elif field.ttype == 'many2many':
                # This a problem caused becouse the line is created before the
                # order
                many_ids = []
                for one_id in eval("local_record."+field.name):
                    field_xmlid = self.env['ir.model.data'].search([
                        ('model', '=', field.relation),
                        ('res_id', '=', one_id.id),
                        ], limit=1)
                    many_ids.append(field_xmlid.complete_name)
                value = {
                    'type': field.ttype,
                    'relation': field.relation,
                    'ids': many_ids
                    }
            elif field.ttype == 'reference':
                # TODO: Test this
                field_content = eval('local_record.'+field.name)
                if not field_content:
                    continue
                relation = field_content._name
                relation_id = field_content.id
                field_xmlid = self.env['ir.model.data'].search([
                    ('model', '=', relation),
                    ('res_id', '=', relation_id)
                    ], limit=1)
                value = {
                    'type': field.ttype,
                    'relation': relation,
                    'id': field_xmlid.complete_name
                    }
            else:
                # This comparation is here becouse global is a reserved word
                if field.name == 'global':
                    value = self.env[xmlid.model].browse(
                        local_record.id)['global']
                else:
                    value = eval('local_record.'+field.name)
            doc[field.name] = value
        return doc


class IrModelDataSyncQueue(models.Model):
    _name = 'ir.model.data.sync.queue'

    name = fields.Char(string='External ID', required=True,)
    vals = fields.Text(string="Values")
    sequence = fields.Integer(string="Sync Sequence")

    @api.multi
    def send_to_couch(self):
        self.ensure_one()
        config = self.env.ref('connector_sincronizador.config')
        url = "http://%s:%s" % (config.couchdb_server, config.couchdb_port)
        couch = couchdb.Server(url=url)
        user = config.couchdb_user
        password = config.couchdb_password
        couch.resource.credentials = (user, password)
        try:
            db = couch[config.couchdb_database]
        except:
            db = couch.create(config.couchdb_database)
        vals = db.get(self.name) or {'_id': self.name}
        for key, val in eval(self.vals).iteritems():
            vals[key] = val
        db.save(vals)
        self.unlink()
        return True

    @api.model
    def create(self, vals):
        res = super(IrModelDataSyncQueue, self).create(vals)
        self.env.ref('connector_sincronizador.config').send_changes_to_couch()
        return res
