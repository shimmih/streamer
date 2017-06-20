import boto3
import json
import sys

class AutoScalingGroup:
	"""Class for AutoScaling Group"""
	def __init__(self, asg_name):
		self.asg_client = boto3.client('autoscaling')
		self.name = asg_name
		self.json = self.asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"][0]
		self.desired = self.json['DesiredCapacity']
		self.min = self.json['MinSize']
		self.max = self.json['MaxSize']
		self.instances = []
		for i in self.json['Instances']:
			self.instances.append(i['InstanceId'])
		data = self.asg_client.describe_tags(Filters=[{'Name': 'auto-scaling-group','Values': [asg_name]}])
		#print data
		self.tags = {}
		for t in data["Tags"]:
                        self.tags[t["Key"]] = t["Value"]
	
	def getInstanceTags(self,*args):
		if len(args) > 0:
			if type(args[0]) == list:
				args = args[0]
		instance_tags_dict = {}
		for i in self.instances:
			instance_tags_dict[i] = {}
		ec2_client = boto3.client('ec2')
		tags = ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':self.instances}])['Tags']
		for tag in tags:
			if len(args) > 0 and tag['Key'] not in args:
				continue
			instance_tags_dict[tag['ResourceId']][tag['Key']] = tag['Value']
		return instance_tags_dict

	

	def findInstances(self,**kwargs):
		'''
		input dictionary of instance-ids tags dictionarys, tag value arguments (tag=value, tag=value...)
		return: list of instances with matching tags
		'''
		if len(kwargs)==0:
			sys.exit("arguments missing")
		instance_list = self.getInstanceTags(kwargs.keys())
		matching_instances = []
		for instance_id,tags in instance_list.iteritems():
			match = 0
			for tag_key,desired_value in kwargs.iteritems():
				try:
					if not tags[tag_key] == desired_value:
						match+=1
				except Exception as e:
					#print 'key {} doest exist'.format(tag_key)
					match+=1
			if match == 0:
				matching_instances.append(instance_id)
		return matching_instances

	def setCapacity(self,new_capacity):
		try:
			response = self.asg_client.set_desired_capacity(
			AutoScalingGroupName=self.name,
			DesiredCapacity=new_capacity,
			HonorCooldown=False
		)
			return response
		except Exception as e:
			raise e

	def addInstances(self,addition):
		new_capacity = self.desired + addition
		return self.setCapacity(new_capacity)

	def getAsgVersion(self):
		'''
		input: dictionary of instance-ids dictionarys with 'version' key
		return: if all same version, version, else error
		'''
		instances = self.getInstanceTags('version')
		instance_list = instances.keys()
		asg_version = ""
		for i in range(0,len(instance_list)-1):
			try:
				if instances[instance_list[i]]['version'] == instances[instance_list[i+1]]['version']:
					asg_version = instances[instance_list[i]]['version']
				else:
					sys.exit("ASG contains mixed instance versions")
			except Exception as e:
				print e
				print instance_list[i] + " has no version tag"
				pass
		return asg_version

	def countVersion(self,new_version):
		'''
		input: dictionary of instance-ids dictionarys with 'version' key, the desired version, and the old(current) version
		returns dictionary with the count of instances with {'new','old','other'} versions
		'''
		instances = self.getInstanceTags('version')
		counts = {}
		versions = []
		for t in instances.values():
			try:
				versions.append(t['version'])
			except Exception as e:
				versions.append('no tag')
		counts['no tag']=versions.count('no tag')
		counts['desired']=versions.count(new_version)
		counts['other'] = len(versions) - counts['desired'] - counts['no tag']
		return counts

	def terminateInstance(self,instance_id):
		'''
		input: instance-id
		'''
		self.asg_client = boto3.client('autoscaling')
		try:
			self.asg_client.terminate_instance_in_auto_scaling_group(InstanceId=instance_id,ShouldDecrementDesiredCapacity=True)
			return "Terminated"
		except Exception as e:
			raise e

	def replaceInstance(self,instance_id):
		'''
		input: instance-id
		'''
		self.asg_client = boto3.client('autoscaling')
		try:
			self.asg_client.terminate_instance_in_auto_scaling_group(InstanceId=instance_id,ShouldDecrementDesiredCapacity=False)
			return "Replaced"
		except Exception as e:
			raise e



# Functions

def findAsgs(**required_tags):
	'''
	input: one or more tags and values as keyword arguments
	returns a list of autoscaling groups with the required tags
	'''
	matching_asgs = []
	asg_client = boto3.client('autoscaling')
	all_asgs = asg_client.describe_auto_scaling_groups()["AutoScalingGroups"]

	for asg in all_asgs:
		# get ASG tags
		asg_tags = asg['Tags']
		current_tags = {}

		for tag in asg_tags:
			# make a dictionary of the required tags and their values
			if tag['Key'] in required_tags.keys():
				current_tags[tag['Key']] = tag['Value']
		# compare the current tags dictionary with the required tags to check if they match
		if cmp(required_tags,current_tags) == 0:
			matching_asgs.append(asg['AutoScalingGroupName'])

	return matching_asgs
