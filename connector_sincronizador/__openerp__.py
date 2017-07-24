# -*- encoding: utf-8 -*-
{
    'name': 'Realtime Sync',
    'description': """

    Makes possible realtime Odoo syncronization between databases
    and store all changes with versioning

    """,
    'category': 'Base',
    'author': 'Marcelo Pickler S.A.',
    'website': 'http://www.sistema.social',
    'version': '0.1',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/connector_sync.xml',
        'views/ir_model.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
