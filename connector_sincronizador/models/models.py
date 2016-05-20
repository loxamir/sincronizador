# -*- coding: utf-8 -*-
from openerp import models, api
import itertools

# special columns automatically created by the ORM
LOG_ACCESS_COLUMNS = ['create_uid', 'create_date', 'write_uid', 'write_date']
MAGIC_COLUMNS = ['id'] + LOG_ACCESS_COLUMNS

''' 
Should be a better way to do that
becouse this way it overides the 
methods but there's should be an 
way to inherit it and just add the 
part that is relevant
'''

class BaseModelSync(models.Model):
    self = models.BaseModel


    @api.model
    @api.returns('self', lambda value: value.id)
    def create_sync(self, vals):
        """ create(vals) -> record

        Creates a new record for the model.

        The new record is initialized using the values from ``vals`` and
        if necessary those from :meth:`~.default_get`.

        :param dict vals:
            values for the model's fields, as a dictionary::

                {'field_name': field_value, ...}

            see :meth:`~.write` for details
        :return: new record created
        :raise AccessError: * if user has no create rights on the requested object
                            * if user tries to bypass access rules for create on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)
        """
        self.check_access_rights('create')

        # add missing defaults, and drop fields that may not be set by user
        vals = self._add_missing_default_values(vals)
        for field in itertools.chain(MAGIC_COLUMNS, ('parent_left', 'parent_right')):
            vals.pop(field, None)

        # split up fields into old-style and pure new-style ones
        old_vals, new_vals, unknown = {}, {}, []
        for key, val in vals.iteritems():
            field = self._fields.get(key)
            if field:
                if field.column or field.inherited:
                    old_vals[key] = val
                if field.inverse and not field.inherited:
                    new_vals[key] = val
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.create() with unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # create record with old-style fields
        record = self.browse(self._create(old_vals))

        # put the values of pure new-style fields into cache, and inverse them
        record._cache.update(record._convert_to_cache(new_vals))
        for key in new_vals:
            self._fields[key].determine_inverse(record)

        #Create an external id for this record
        #if record._name not in ['ir.model.data']:
        dont_sync_models = ['ir.model.data', 'ir.model.data.sync']
        for model in self.env['ir.model'].search([('osv_memory','=',True)]):
            dont_sync_models.append(model.name)

        if self._name not in dont_sync_models and 'synchronized' not in self.env.context:
            #xml_id_record = record.__export_xml_id()
            xml_id = record.__export_xml_id().split(".")
            xml_id_record = self.env['ir.model.data'].sudo().search([
                ('module','=',xml_id[0]),
                ('name','=',xml_id[1])
                ])
            xml_id_record.synchronized = False
            xml_id_record.sudo().send_this_to_couch()
        print "Create"
        return record

    @api.multi
    def write_sync(self, vals):
        """ write(vals)

        Updates all records in the current set with the provided values.

        :param dict vals: fields to update and the value to set on them e.g::

                {'foo': 1, 'bar': "Qux"}

            will set the field ``foo`` to ``1`` and the field ``bar`` to
            ``"Qux"`` if those are valid (otherwise it will trigger an error).

        :raise AccessError: * if user has no write rights on the requested object
                            * if user tries to bypass access rules for write on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        * For numeric fields (:class:`~openerp.fields.Integer`,
          :class:`~openerp.fields.Float`) the value should be of the
          corresponding type
        * For :class:`~openerp.fields.Boolean`, the value should be a
          :class:`python:bool`
        * For :class:`~openerp.fields.Selection`, the value should match the
          selection values (generally :class:`python:str`, sometimes
          :class:`python:int`)
        * For :class:`~openerp.fields.Many2one`, the value should be the
          database identifier of the record to set
        * Other non-relational fields use a string for value

          .. danger::

              for historical and compatibility reasons,
              :class:`~openerp.fields.Date` and
              :class:`~openerp.fields.Datetime` fields use strings as values
              (written and read) rather than :class:`~python:datetime.date` or
              :class:`~python:datetime.datetime`. These date strings are
              UTC-only and formatted according to
              :const:`openerp.tools.misc.DEFAULT_SERVER_DATE_FORMAT` and
              :const:`openerp.tools.misc.DEFAULT_SERVER_DATETIME_FORMAT`
        * .. _openerp/models/relationals/format:

          :class:`~openerp.fields.One2many` and
          :class:`~openerp.fields.Many2many` use a special "commands" format to
          manipulate the set of records stored in/associated with the field.

          This format is a list of triplets executed sequentially, where each
          triplet is a command to execute on the set of records. Not all
          commands apply in all situations. Possible commands are:

          ``(0, _, values)``
              adds a new record created from the provided ``value`` dict.
          ``(1, id, values)``
              updates an existing record of id ``id`` with the values in
              ``values``. Can not be used in :meth:`~.create`.
          ``(2, id, _)``
              removes the record of id ``id`` from the set, then deletes it
              (from the database). Can not be used in :meth:`~.create`.
          ``(3, id, _)``
              removes the record of id ``id`` from the set, but does not
              delete it. Can not be used on
              :class:`~openerp.fields.One2many`. Can not be used in
              :meth:`~.create`.
          ``(4, id, _)``
              adds an existing record of id ``id`` to the set. Can not be
              used on :class:`~openerp.fields.One2many`.
          ``(5, _, _)``
              removes all records from the set, equivalent to using the
              command ``3`` on every record explicitly. Can not be used on
              :class:`~openerp.fields.One2many`. Can not be used in
              :meth:`~.create`.
          ``(6, _, ids)``
              replaces all existing records in the set by the ``ids`` list,
              equivalent to using the command ``5`` followed by a command
              ``4`` for each ``id`` in ``ids``. Can not be used on
              :class:`~openerp.fields.One2many`.

          .. note:: Values marked as ``_`` in the list above are ignored and
                    can be anything, generally ``0`` or ``False``.
        """
        if not self:
            return True

        self._check_concurrency(self._ids)
        self.check_access_rights('write')

        # No user-driven update of these columns
        for field in itertools.chain(MAGIC_COLUMNS, ('parent_left', 'parent_right')):
            vals.pop(field, None)

        # split up fields into old-style and pure new-style ones
        old_vals, new_vals, unknown = {}, {}, []
        for key, val in vals.iteritems():
            field = self._fields.get(key)
            if field:
                if field.column or field.inherited:
                    old_vals[key] = val
                if field.inverse and not field.inherited:
                    new_vals[key] = val
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.write() with unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # write old-style fields with (low-level) method _write
        if old_vals:
            self._write(old_vals)

        # put the values of pure new-style fields into cache, and inverse them
        if new_vals:
            for record in self:
                record._cache.update(record._convert_to_cache(new_vals, update=True))
            for key in new_vals:
                self._fields[key].determine_inverse(self)

        # This is to avoid loop and errors
        dont_sync_models = ['ir.model.data', 'ir.model.data.sync']

        # This is to avoid and unnecessary models
        for model in self.env['ir.model'].search([('osv_memory','=',True)]):
            dont_sync_models.append(model.name)

        if self._name not in dont_sync_models and 'synchronized' not in self.env.context:
            xml_id = self.__export_xml_id().split(".")
            xml_id_record = self.env['ir.model.data'].sudo().search([
                ('module','=',xml_id[0]),
                ('name','=',xml_id[1])
                ])
            xml_id_record.synchronized = False
            xml_id_record.sudo().send_this_to_couch()

        print "Write"

        return True


    def unlink_sync(self, cr, uid, ids, context=None):
        """ unlink()

        Deletes the records of the current set

        :raise AccessError: * if user has no unlink rights on the requested object
                            * if user tries to bypass access rules for unlink on the requested object
        :raise UserError: if the record is default property for other records

        """
        '''if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        result_store = self._store_get_values(cr, uid, ids, self._fields.keys(), context)

        # for recomputing new-style fields
        recs = self.browse(cr, uid, ids, context)
        recs.modified(self._fields)

        self._check_concurrency(cr, ids, context)

        self.check_access_rights(cr, uid, 'unlink')

        ir_property = self.pool.get('ir.property')

        # Check if the records are used as default properties.
        domain = [('res_id', '=', False),
                  ('value_reference', 'in', ['%s,%s' % (self._name, i) for i in ids]),
                 ]
        if ir_property.search(cr, uid, domain, context=context):
            raise except_orm(_('Error'), _('Unable to delete this document because it is used as a default property'))

        # Delete the records' properties.
        property_ids = ir_property.search(cr, uid, [('res_id', 'in', ['%s,%s' % (self._name, i) for i in ids])], context=context)
        ir_property.unlink(cr, uid, property_ids, context=context)

        self.delete_workflow(cr, uid, ids, context=context)

        self.check_access_rule(cr, uid, ids, 'unlink', context=context)
        pool_model_data = self.pool.get('ir.model.data')
        ir_values_obj = self.pool.get('ir.values')
        ir_attachment_obj = self.pool.get('ir.attachment')
        for sub_ids in cr.split_for_in_conditions(ids):
            cr.execute('delete from ' + self._table + ' ' \
                       'where id IN %s', (sub_ids,))

            # Removing the ir_model_data reference if the record being deleted is a record created by xml/csv file,
            # as these are not connected with real database foreign keys, and would be dangling references.
            # Note: following steps performed as admin to avoid access rights restrictions, and with no context
            #       to avoid possible side-effects during admin calls.
            # Step 1. Calling unlink of ir_model_data only for the affected IDS
            reference_ids = pool_model_data.search(cr, SUPERUSER_ID, [('res_id','in',list(sub_ids)),('model','=',self._name)])
            # Step 2. Marching towards the real deletion of referenced records
            if reference_ids:
                pool_model_data.unlink(cr, SUPERUSER_ID, reference_ids)

            # For the same reason, removing the record relevant to ir_values
            ir_value_ids = ir_values_obj.search(cr, uid,
                    ['|',('value','in',['%s,%s' % (self._name, sid) for sid in sub_ids]),'&',('res_id','in',list(sub_ids)),('model','=',self._name)],
                    context=context)
            if ir_value_ids:
                ir_values_obj.unlink(cr, uid, ir_value_ids, context=context)

            # For the same reason, removing the record relevant to ir_attachment
            # The search is performed with sql as the search method of ir_attachment is overridden to hide attachments of deleted records
            cr.execute('select id from ir_attachment where res_model = %s and res_id in %s', (self._name, sub_ids))
            ir_attachment_ids = [ir_attachment[0] for ir_attachment in cr.fetchall()]
            if ir_attachment_ids:
                ir_attachment_obj.unlink(cr, uid, ir_attachment_ids, context=context)

        # invalidate the *whole* cache, since the orm does not handle all
        # changes made in the database, like cascading delete!
        recs.invalidate_cache()

        for order, obj_name, store_ids, fields in result_store:
            if obj_name == self._name:
                effective_store_ids = set(store_ids) - set(ids)
            else:
                effective_store_ids = store_ids
            if effective_store_ids:
                obj = self.pool[obj_name]
                cr.execute('select id from '+obj._table+' where id IN %s', (tuple(effective_store_ids),))
                rids = map(lambda x: x[0], cr.fetchall())
                if rids:
                    obj._store_set_values(cr, uid, rids, fields, context)

        # recompute new-style fields
        recs.recompute()'''
        super(BaseModelSync, self).unlink(cr, uid, ids, context=None)
        print "Unlink"

        ''' 
        dont_sync_models = ['ir.model.data', 'ir.model.data.sync']

        # This is to avoid and unnecessary models
        model_obj = self.pool.get()
        for model in model_obj.search([('osv_memory','=',True)]):
            print model.name
            dont_sync_models.append(model.name)

        if self._name not in dont_sync_models and 'synchronized' not in self.env.context:
            xml_id = self.__export_xml_id().split(".")
            xml_id_record = self.env['ir.model.data'].sudo().search([
                ('module','=',xml_id[0]),
                ('name','=',xml_id[1])
                ])
            xml_id_record.unlinked = True
            xml_id_record.sudo().send_this_to_couch()
        '''

        return True

    #models.Model.create = create_sync
    #models.Model.write = write_sync
class teste(object):
    def unlink_syncs(self, cr, uid, ids, context=None):
        model_inheritance = models.Model().unlink(cr, uid, ids, context=None)
        print model_inheritance
        #.unlink(cr, uid, ids, context=None)
        #model_inheritance.unlink(cr, uid, ids, context=None)
        print "Foi Unlink"
        return True

    models.Model.unlink = unlink_syncs