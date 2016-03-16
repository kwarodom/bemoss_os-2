#!/bin/sh
#Author: BEMOSS Team

#Download the package lists from the repositories and update them
sudo apt-get update
#Download and install the dependencies of the BEMOSS platform
sudo apt-get install build-essential openssl git g++ libxml2-dev libxslt1-dev python-dev libevent-dev libssl-dev python-tk python-pip libffi-dev libpq-dev python-psycopg2 python-zmq gnome-terminal --assume-yes
sudo pip install netifaces networkx colormath
sudo mkdir ~/workspace
#Remove the existing bemoss_os folder
sudo rm -rf ~/workspace/bemoss_os
#Clone the bemoss_os repository
cd ~/workspace
sudo git clone -b master https://github.com/bemoss/bemoss_os.git
sudo chmod 777 -R ~/workspace
#Compile dependency codes in C/C++
cd ~/workspace
cd ~/workspace/bemoss_os/bemoss_lib/protocols/BACnet/bacnet-stack-0.8.2
sudo make clean all
#Go to the bemoss_os folder and run the bootstrap command 
cd ~/workspace/bemoss_os
sudo python bootstrap.py
#Remove colormath egg files and copy modified colormath library folder
sudo rm -rf ~/workspace/bemoss_os/env/lib/python2.7/site-packages/colormath
sudo cp -a ~/workspace/bemoss_os/bemoss_lib/custom-eggs/colormath-2.0.2-py2.7.egg/colormath ~/workspace/bemoss_os/env/lib/python2.7/site-packages
#Download and install the dependencies for web_UI
sudo pip install django==1.4
sudo pip install tornado
sudo pip install six
sudo pip install tablib
sudo pip install pyzmq --upgrade --install-option="--zmq=bundled"
sudo apt-get install python-pandas --assume-yes
sudo ldconfig
#Download and install the dependencies of the postgresql database
sudo apt-get install postgresql postgresql-contrib python-yaml --assume-yes
cd ~/workspace
#Remove the existing bemoss_web_ui folder
sudo rm -rf bemoss_web_ui
#Clone the bemoss_web_ui repository
# TODO: switch to GitHub repo
sudo git clone -b master https://github.com/bemoss/bemoss_web_ui.git
sudo chmod 777 -R ~/workspace
#Create the bemossdb database
sudo -u postgres psql -c "CREATE USER admin WITH PASSWORD 'admin';"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS bemossdb;"
sudo -u postgres createdb bemossdb -O admin
sudo -u postgres psql -d bemossdb -c "create extension hstore;"
# Install Dependencies for Cassandra
sudo apt-get update
sudo apt-get install openjdk-7-jre --assume-yes
sudo apt-get install libjna-java --assume-yes
# Install Cassandra
cd ~/workspace
wget http://downloads.datastax.com/community/dsc-cassandra-2.1.7-bin.tar.gz
tar -xvzf dsc-cassandra-2.1.7-bin.tar.gz
sudo rm dsc-cassandra-2.1.7-bin.tar.gz 
sudo mv dsc-cassandra-2.1.7 cassandra
# Install Dependencies in virtual env.
cd ~/workspace/bemoss_os/env
. bin/activate
pip install -r ~/workspace/bemoss_os/requirements.txt
# Install Cassandra Driver
# (For better performance of Cassandra, the install-option can be removed but might cause installation failure in some boards.)
sudo CASS_DRIVER_NO_CYTHON=1 pip install cassandra-driver
CASS_DRIVER_NO_CYTHON=1 pip install cassandra-driver
deactivate
#Go to the bemoss_web_ui and run the syncdb command for the database tables (ref: model.py)
cd ~/workspace/bemoss_os
sudo python ~/workspace/bemoss_web_ui/manage.py syncdb
sudo python ~/workspace/bemoss_web_ui/run/defaultDB.py
#Initialize the tables
sudo python ~/workspace/bemoss_os/bemoss_lib/utils/platform_initiator.py
# Prompt user for Cassandra Authorization Info
sudo python ~/workspace/bemoss_os/bemoss_lib/databases/cassandraAPI/initialize.py
# Fix miscellaneaus issues
sudo ~/workspace/bemoss_os/bemoss_lib/utils/increase_open_file_limit.sh
rm ~/workspace/bemoss_os/bemoss_lib/utils/increase_open_file_limit.sh
mkdir -p ~/.volttron/agents
# Prompt user to reboot
echo "BEMOSS Installation is complete!"
echo "Before running BEMOSS for the first time, reboot is required. Do you want to reboot now (yes/no)?:"
read CHOICE
if [ "$CHOICE" = "yes" ] || [ "$CHOICE" = "y" ]; then
	sudo reboot
else
	echo "Reboot cancelled! Please manually reboot before using BEMOSS."
fi
