# Sincronizador Online/Offline

The Sincronizador allow the user work locally with a server and synchronize the data in real time while there's internet, when the internet goes down it keep the system working and synchronize every document when the internet came back
Have a track of every change made on odoo documents with coudhdb version system

# The requisites:
Working Couchdb 2 server
Working Odoo 8 server
Technical skils ;)

# How to install
1 - Clone this repository
2 - Copy the directory "connector_sincronizador" to your odoo addons directory
3 - pip install couchdb
4 - pip install toposort
5 - Install the module "connector_sincronizador" on Odoo
6 - Go to Settings/Technical/Database Structure/Synchronism, Click on the button "First Time" and wait it finish
7 - Go to your couchdb and check the new coudhdb database with all your odoo documents, now all your changes to odoo documents will be sent to couchdb (The odoo documents will be referenced by it's XML IDs on Couchdb)
8 - Go to Settings/Technical/Database Structure/Synchronism and Click on the button "Get Sync Continuous"(this will never end, so open other browser tab)
9 - Change the admin username on Odoo and see the changes on Couchdb
10 - Change the admin username on Couchdb and see the changes on Odoo
11 - To make the synchronization work between two databases, you have repeat the steps 1-10 for other database and sync them with couchdb continuous replication

# How to use
Just use the odoo, all the changes made on one database will be synchronized in realtime to the others

# Need help?
I work for 10 Dolares per hour, so it's cheap, contact at loxamir@gmail.com
