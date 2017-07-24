
# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api

import logging
_logger = logging.getLogger(__name__)


class IrModel(models.Model):
    _inherit = "ir.model"

    sincronizable = fields.Boolean(
        string="Sincronizable",
        default=True,
        )
