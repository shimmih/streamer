import boto3
import urllib2

class LocalInstance:
	"""Class for an instance from within the instance"""
	#id, az, region, env, vpc_id, vpc_name, userdata, tags (dictionary), instance (boto3 resource)#
	def __init__(self):
		self.metadata_path = 'http://169.254.169.254/latest/meta-data/'
		self.id = urllib2.urlopen(self.metadata_path+'instance-id').read()
		self.az = urllib2.urlopen(self.metadata_path + 'placement/availability-zone').read()
		self.region = self.az[:-1]
		self.ec2 = boto3.resource('ec2',self.region)
		self.instance = self.ec2.Instance(self.id)
		self.tags = {}
		for t in self.instance.tags:
			self.tags[t["Key"]] = t["Value"]
		try:
			self.userdata = urllib2.urlopen('http://169.254.169.254/latest/user-data/').read()
		except Exception as e:
			print "instance has no userdata"
		try:	
			self.vpc_id = self.instance.vpc_id
			for t in self.instance.vpc.tags:
				if t['Key'].lower() == 'name':
					self.vpc_name = t['Value'].lower()
		except:
			print "instance is not in a vpc"
		try:
			self.env = self.tags['env'].lower()
			self.component = self.tags['Component'].lower()
		except:
			print "no env or Component tag"
	
	def getMetadata(self,data):
		return urllib2.urlopen(self.metadata_path + data).read()

	def  setTag(self,key,value):
		self.instance.create_tags(Tags=[{'Key':key,'Value':value}])
	
	def splunkInit(self):
		print "SplunkInit function called"
		meta_fields = "vpc::{} env::{}".format(self.vpc_name,self.env)
		serverName = "aws::"+self.vpc_name+"::"+self.region+"::"+self.component+"::"+self.id
		serverName = serverName.replace(" ","") # Remove spaces if exist
		platform = self.instance.platform

		if platform == 'windows':
			inputsFile = "C:\\Program Files\\SplunkUniversalForwarder\\etc\\system\\local\\inputs.conf"
		else:
			inputsFile = "/opt/splunkforwarder/etc/system/local/inputs.conf"

		try:
			inputs = open(inputsFile, "wb" )
		except Exception as e:
			print "creating a new inputs file failed!"
			print e
		# writing configuration to inputs file
		try:
			inputs.write ("[default]\nhost = "+serverName+"\n_meta = "+meta_fields+"\n")
		except Exception as e:
			print "Writing server name to inputs file failed!"
			print e
		# closing open file
		inputs.close()
		import os
		if platform == 'windows':
			try:
				os.system('sc stop SplunkForwarder')
			except Exception as e:
				print e
			os.system('sc start SplunkForwarder')
		else:
			try:
				os.system("sudo /opt/splunkforwarder/bin/splunk stop")
			except Exception as e:
				print e
			os.system("sudo /opt/splunkforwarder/bin/splunk --accept-license start")
		print "Splunk initialized successfully"
