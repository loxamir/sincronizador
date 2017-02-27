# -*- encoding: utf-8 -*-
{
    'name': 'Connector Sync',
    'description': """

    Connector Sync

    """,
    'category': 'Base',
    'author': 'Marcelo Pickler S.A.',
    'website': 'http://www.sistema.social',
    'version': '0.1',
    'depends': [
        'base',
    ],
    'data': [
        #'security/groups.xml',
        #'security/ir.model.access.csv',
        'views/connector_sync.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
