# -*- coding: utf-8 -*-
from openerp import models, fields, api
import couchdb
import itertools

couch_database = 'python2'

class IrModelDataSync(models.Model):
    _name = 'ir.model.data.sync'

    server = fields.Char(string="Server")
    last_seq = fields.Integer(string="Last Sequence")

    @api.multi
    def create_couch2(self, res_id):
        register = self.env['ir.model.data.sync.queue'].search([('id','=',res_id)])
        xmlid_split = register.name.split('.')
        texto = xmlid_split[1]
        if len(xmlid_split)>2:
            texto = ""
            for text in xmlid_split[1:]:
                texto = texto+"."+text

        print texto
        xml_id_record = self.env['ir.model.data'].search([
            ('module','=',xmlid_split[0]),
            ('name','=',texto)
            ])
        self.create_couch(xml_id_record)
        register.unlink()
        return True

    @api.model
    def create_couch(self, xmlid):     
        couch = couchdb.Server()
        db = couch[couch_database]
        
        if xmlid.res_id == 0:
            return
        local_record = self.env[xmlid.model].search([('id','=',xmlid.res_id)])
        doc = xmlid._id and db.get(xmlid._id) or {'xml_id': xmlid.complete_name}
        
        print "create_couch(%s)"%xmlid.complete_name
        
        # Create a document with all fields
        dont_sync_fields = ['__last_update','id']
        field_list = self.env['ir.model.fields'].search([
            ('model_id','=', xmlid.model),
            ('name','not in', dont_sync_fields)
        ])

        formated_fields = self.format_fields(local_record, xmlid, field_list)
        doc = dict(doc.items() + formated_fields.items())

        if xmlid.model == 'mail.message':
            doc['res_xmlid'] = self.env['ir.model.data'].search([
                ('model','=',doc['model']),
                ('res_id','=',doc['res_id'])
                ]).complete_name
        doc['odoo_model'] = xmlid.model
        doc['server'] = self.env['ir.model.data.sync'].search([], limit=1).server
        db.save(doc)
        if not xmlid._id:
            xmlid._id =  doc['_id']
        xmlid.synchronized = True
        # Resend data
        #if len(formated_fields[1])>0:
        #    for one_xmlid in formated_fields[1]:
        #        self.create_couch(one_xmlid)
        return True

    @api.model
    def write_couch(self, xmlid, vals):     
        couch = couchdb.Server()
        db = couch[couch_database]
        
        if xmlid.res_id == 0:
            return
        local_record = self.env[xmlid.model].search([('id','=',xmlid.res_id)])
        doc = xmlid._id and db.get(xmlid._id) or {'xml_id': xmlid.complete_name}

        print "write_couch(%s, %s)"%(xmlid.complete_name, vals)

        # Avoid some fields in couch
        dont_sync_fields = ['__last_update','id']
        field_list = []
        for field in vals.keys():
            if field in dont_sync_fields:
                field_list.pop(field, None)
            else:
                field_obj = self.env['ir.model.fields'].search([
                    ('model','=', xmlid.model),
                    ('name','=', field)
                    ])
                field_list.append(field_obj)
                #xmlid.model.field_id.field

        formated_fields = self.format_fields(local_record, xmlid, field_list)
        doc = dict(doc.items() + formated_fields.items())
        
        if xmlid.model == 'mail.message':
            # Add the res_xmlid field to get the remote res_id correctly
            doc['res_xmlid'] = self.env['ir.model.data'].search([
                ('model','=',doc['model']),
                ('res_id','=',doc['res_id'])
                ]).complete_name

        doc['odoo_model'] = xmlid.model
        doc['server'] = self.env['ir.model.data.sync'].search([], limit=1).server
        db.save(doc)
        if not xmlid._id:
            xmlid._id =  doc['_id']
        xmlid.synchronized = True

        # Resend one2many fields 
        #if len(formated_fields[1])>0:
        #    for one_xmlid in formated_fields[1]:
        #        self.write_couch(one_xmlid)
        return True        

    @api.model
    def unlink_couch(self, xmlid, vals):     
        couch = couchdb.Server()
        db = couch[couch_database]
        if xmlid.unlinked:
            if '_id' in doc:
                #if this already exist in couchdb, mark it to as unlinked
                doc['unlinked'] = True
                db.save(doc)
                print "delete %s"%xmlid.complete_name
            #self.unlink()
        return True

    @api.multi
    def send_all_to_couch(self):  
        """
        All register have to have external_id
        """
        # Time with couchdb saving ervery register 6:55
        # Time without couchdb 0:25
        # Time saving in every model 3:15
        # Time saving just at the end: 3:11
        # Conclusion: the command db.get(external_id) is what make this slow

        print "Preparing all data"
        couch = couchdb.Server()
        db = couch[couch_database]
        dont_sync_models = ['ir.model.data', 'ir.model.data.sync', 'ir.model.data.sync.queue']
        all_models = self.env['ir.model'].search([
            ('osv_memory','=',False),
            ('model','not in', dont_sync_models),
            #('model','in', ['res.users'])
            ])
        unused_fields = ['id', '__last_update', 'global']
        
        for model in all_models:
            if not self.env['ir.model.fields'].search([
                ('name','=','create_uid'),
                ('model_id','=',model.model)
                ]):
                continue
            all_records = self.env[model.model].search([])
            for record in all_records:
                all_fields = record._fields
                external_id = record.get_external_id().values()[0]
                all_values = db.get(external_id) or {'_id': external_id}
                tmp_doc = all_values.copy()

                for field in all_fields:
                    if field in unused_fields or not eval('record.'+field):
                        continue
                    if all_fields[field].type == 'many2one':
                        field_external_id = eval('record.'+field).get_external_id().values()[0]
                        all_values[field] = field_external_id
                    elif all_fields[field].type == 'one2many':
                        continue
                    elif all_fields[field].type == 'many2many':
                        all_values[field] = eval('record.'+field).get_external_id().values()
                    elif all_fields[field].type == 'reference':
                        #TODO: FIX this
                        print "reference"
                        continue
                    else:
                        all_values[field] = eval('record.'+field)
                print 'external_id %s'%all_values['_id']
                if tmp_doc != all_values.copy():
                    db.save(all_values)
        return True  

    @api.multi
    def send_all_to_couch_old(self):  
        print "Start Sending all to couchdb"   
        couch = couchdb.Server()
        #db = couch[self.pool.db.dbname]
        db = couch[couch_database]

        dont_sync_models = ['ir.model.data', 'ir.model.data.sync', 'ir.model.data.sync.queue']

        # This is to avoid and unnecessary models
        for model in self.env['ir.model'].search([('osv_memory','=',True)]):
            dont_sync_models.append(model.name)

        print "Will send all except:\n%s"%dont_sync_models
        xmlid_list = self.env['ir.model.data'].search([
            ('synchronized','=', False),
            ('model', 'not in' , dont_sync_models),
            ])
        
        for xmlid in xmlid_list:
            self.create_couch(xmlid)
        return True  

    @api.multi
    def create_xmlid_for_everything(self):   
        """
        Create XMLID for every register in every model
        """  

        dont_sync_models = ['ir.model.data', 'ir.model.data.sync']
        models = []

        for model in self.env['ir.model'].search([
            ('osv_memory','!=',True),
            ('name','not in',dont_sync_models)
            ]):
            #print "Model: %s"%(model.model)
            if not self.env['ir.model.fields'].search([('model_id','=',model.id),('name','=','write_date')]):
                continue
            #try:
            registers = self.env[model.model].search([])
            #except:
            #    print "Problemas en %s"%model.model
            #    self.env.cr.rollback()
            #    continue
            for register in registers:
                #the register already have xml id
                if self.env['ir.model.data'].search([
                    ('model','=',model.model),
                    ('res_id','=',register.id)
                    ]):
                    continue
                xml_id = self.create_xml_id(model.model, register.id)
                #self.env.cr.commit()
                #xml_id = register.__export_xml_id()
                #print "ID: %s, XML_ID: %s"%(register.id, xml_id)
                
        return True 

    @api.multi
    def import_doc(self, doc):     
        couch = couchdb.Server()
        #db = couch[self.pool.db.dbname]
        db = couch[couch_database]

        #print "modelo = %s"%doc
        if doc['odoo_model'] == 'im_chat.message':
            from_uid = self.env.ref(doc['from_id']['id']).id
            uuid = self.env.ref(doc['to_id']['id']).uuid
            message_type = doc['type']
            message_content = doc['message']
            self.env['im_chat.message'].with_context({'synchronized': True}).post(from_uid, uuid, message_type, message_content)
        
        else:

            reserved_fields = ['_rev','new_password']
            vals = {}
            exceptions = [{
            'model': 'stock.move',
            'field': 'product_qty'
            }]

            for key in doc:
                ignore_field = False
                # Here we managed some wear exceptions
                for exception in exceptions:
                    if doc['odoo_model'] == exception['model'] and key == exception['field']:
                        ignore_field = True
                        continue
                if ignore_field:
                    continue

                value = doc[key]
                if key in reserved_fields:
                    continue
                if type(value) is dict:
                    if value['type'] == 'many2one':
                        vals[key+"/id"] = value['id']

                    elif value['type'] == 'one2many':
                        continue

                    elif value['type'] == 'many2many':
                        if len(value['ids']) == 0:
                            continue
                        many_ids = ""
                        for one_xmlid in value['ids']:
                            many_ids += one_xmlid+","
                        vals[key+"/id"] = many_ids[:-1] # This remove the last ","

                    if value['type'] == 'reference':
                        registro = self.env.ref(value['id'])
                        vals[key] = "%s,%s"%(value['relation'], registro.id)

                else:

                    if key == 'xml_id':
                        continue
                    elif key == '_id':
                        continue
                    elif key == 'odoo_model':
                        model = value
                    elif key == 'model':  #TODO: Remove this! It's just a temporary fix, Remove this after new database
                        if not 'odoo_model' in doc:
                            model = value
                        else:
                            vals[key] = value

                    else:
                        if type(value) == bool and value==True:
                            vals[key] = str(value)
                        elif value == False:
                            vals.pop(key, None)
                        else:
                            vals[key] = value

            vals['id'] = doc['xml_id']
            
            #correct the local value for the chatter
            if model == 'mail.message':
                vals['res_id'] = self.env.ref(doc['res_xmlid']).id
                vals.pop('res_xmlid', None)
            else:
                vals.pop('model', None)
            #print "XML_ID: %s"%doc['xml_id']
            print "model=%s"%model
            print "vals: %s"%vals
            res = self.env[model].with_context({'synchronized': True, 'tracking_disable': True, 'mail_create_nosubscribe': True}).load(vals.keys(),[vals.values()])
        return res        

    def create_xml_id(self, model, id):
        """ Return a valid xml_id for the record ``self``. """
        postfix = 0
        name = '%s_%s' % (model, id)
        ir_model_data = self.env['ir.model.data']
        while ir_model_data.search([('module', '=', 'export__'), ('name', '=', name)]):
            postfix += 1
            name = '%s_%s_%s' % (model, id, postfix)
        ir_model_data.create({
            'model': model,
            'res_id': id,
            'module': 'export__',
            'name': name,
        })
        return 'export__.' + name

    @api.model
    def format_fields(self, local_record, xmlid, field_list):
        #resend_ids = []
        doc = {}
        for field in field_list:
            # This comparation is usefull to make the process faster and without strange 
            # warnings and errors 
            if field.ttype == 'many2one':
                field_xmlid = self.env['ir.model.data'].search([
                    ('model','=',field.relation),
                    ('res_id','=',eval("local_record."+field.name+".id"))
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
                # This a problem caused becouse the line is created before the order
                many_ids = []
                one2many_ids = eval("local_record."+field.name)
                if len(one2many_ids.ids) == 0 or one2many_ids._name == xmlid.model:
                    #print "continuing %s %s"%(field.name, one2many_ids)
                    continue
                #print "one2many_ids %s"%eval("local_record."+field.name)
                for one_id in eval("local_record."+field.name):
                    field_xmlid = self.env['ir.model.data'].search([
                        ('model','=',field.relation),
                        ('res_id','=', one_id.id),
                        ], limit=1)
                    many_ids.append(field_xmlid.complete_name)
                    #resend_ids.append(field_xmlid)
                    #print resend_ids
                #    self.send_to_couch(field_xmlid)
                value = {
                    'type': field.ttype,
                    'relation': field.relation,
                    'ids': many_ids
                    }
            elif field.ttype == 'many2many':
                # This a problem caused becouse the line is created before the order
                many_ids = []
                for one_id in eval("local_record."+field.name):
                    field_xmlid = self.env['ir.model.data'].search([
                        ('model','=',field.relation),
                        ('res_id','=', one_id.id),
                        ], limit=1)
                    many_ids.append(field_xmlid.complete_name)
                value = {
                    'type': field.ttype,
                    'relation': field.relation,
                    'ids': many_ids
                    }
            elif field.ttype == 'reference':
                #TODO: Test this
                field_content = eval('local_record.'+field.name)
                #print "field %s -- content %s"%(field.name, field_content.name)
                if not field_content:
                    continue
                relation = field_content._name
                relation_id = field_content.id
                field_xmlid = self.env['ir.model.data'].search([
                    ('model','=',relation),
                    ('res_id','=',relation_id)
                    ], limit=1)
                value = {
                    'type': field.ttype,
                    'relation': relation,
                    'id': field_xmlid.complete_name
                    }
            else:
                # This comparation is here becouse global is a reserved word
                if field.name == 'global':
                    value = self.env[xmlid.model].browse(local_record.id)['global']
                else:
                    value = eval('local_record.'+field.name)
            doc[field.name] = value
        return doc#, resend_ids

class IrModelDataSyncQueue(models.Model):
    _name = 'ir.model.data.sync.queue'

    #xml_id = fields.Many2one('ir.model.data', string="Document XML ID")
    name = fields.Char(string='Name')
    vals = fields.Text(string="Values")
    #_id = fields.Char(string="Global ID")
    method = fields.Selection([
        ('create','Create'),
        ('write','Write'),
        ('unlink','Remove')
        ], string="Method")


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    _id = fields.Char(string="Global ID")
    synchronized = fields.Boolean(string="Synchornized")
    unlinked = fields.Boolean(string="Unlinked") 


