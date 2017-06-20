import boto3
import sys

# General
def getKwArgs(arguments):
	'''
	input: sys.argv
	retun: dictionary with all keword arguments (x=y)
	'''
	args = {}
	for i in arguments:
		try:
			k,v = i.split('=')
			args[k] = v
		except Exception as e:
			pass
	return args
# ASG
def getAsgState(asg_name, tags):
	asg_detail = getAsgDetail(asg_name)
	asg_instances = getAsgInstances(asg_detail)
	instances_tags = getInstanceTags(asg_instances,tags)
	return instances_tags

def getAsgDetail(asg):
	'''
	input asg name
	return: asg description json

	'''
	if type(asg) == str:
		asg = [asg]
	asg_client = boto3.client('autoscaling')
	return asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=asg)["AutoScalingGroups"][0]

def getAsgDesiredCapacity(asg):
	'''
	input: asg description json
	return: desired capacity
	'''
	return asg['DesiredCapacity']

def getAsgMinCapacity(asg):
	'''
	input: asg description json
	return: minimum capacity
	'''
	return asg['MinSize']

def getAsgMaxCapacity(asg):
	'''
	input: asg description json
	return: max capacity
	'''
	return asg['MaxSize']

def setAsgDesiredCapacity(asg_name,capacity):
	'''
	input: asg name, new desired capacity
	return: desired capacity
	'''
	asg_client = boto3.client('autoscaling')
	try:
		response = asg_client.set_desired_capacity(
			AutoScalingGroupName=asg_name,
			DesiredCapacity=capacity,
			HonorCooldown=False
		)
		status_code = response['ResponseMetadata']['HTTPStatusCode']
		if status_code == 200:
			print '\nSuccess.'
		return capacity
	except:
		print '\nFailure.'
		raise

def getAsgInstances(asg):
	'''
	input: asg description json
	return: list of instance ids
	'''
	asg_instances = []
	asg_client = boto3.client('autoscaling')
	for i in asg['Instances']:
		asg_instances.append(i['InstanceId'])
	return asg_instances

def getInstanceTags(instance_list,tag_list):
	'''
	input: list of instance-ids, list of required tags
	return: dictionary with a key for each instace-id containing it's requested tags
	'''
	instance_tags_dict = {}
	for i in instance_list:
		instance_tags_dict[i] = {}
	ec2_client = boto3.client('ec2')
	tags = ec2_client.describe_tags(Filters=[{'Name':'resource-id', 'Values':instance_list}])['Tags']
	for tag in tags:
		if tag['Key'] in tag_list:
			instance_tags_dict[tag['ResourceId']][tag['Key']] = tag['Value']
	return instance_tags_dict

def getAsgVersion(instances):
	'''
	input: dictionary of instance-ids dictionarys with 'version' key
	return: if all same version, version, else error
	'''
	instance_list = instances.keys()
	for i in range(0,len(instance_list)-1):
		try:
			if instances[instance_list[i]]['version'] == instances[instance_list[i+1]]['version']:
				asg_version = instances[instance_list[i]]['version']
			else:
				sys.exit("ASG contains mixed instance versions")
		except Exception as e:
			print e
			print instance_list[i] + " has no version tag"
			sys.exit("ASG contains mixed instance versions")
	return asg_version

def countVersions(instances,newv):
	'''
	input: dictionary of instance-ids dictionarys with 'version' key, the desired version, and the old(current) version
	returns dictionary with the count of instances with {'new','old','other'} versions
	'''
	counts = {}
	versions = []
	for t in instances.values():
		try:
			versions.append(t['version'])
		except Exception as e:
			versions.append('no tag')
	counts['no tag']=versions.count('no tag')
	counts['desired']=versions.count(newv)
	counts['other'] = len(versions) - counts['desired'] - counts['no tag']
	return counts

def findInstance(instance_list,**kwargs):
	'''
	input dictionary of instance-ids tags dictionarys, tag value arguments (tag=value, tag=value...)
	return: list of instances with matching tags
	'''
	if len(instance_list)==0 or len(kwargs)==0:
		return "arguments missing"
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

def terminateAsgInstance(instance_id):
	'''
	input: instance-id
	'''
	asg_client = boto3.client('autoscaling')
	try:
		asg_client.terminate_instance_in_auto_scaling_group(InstanceId=instance_id,ShouldDecrementDesiredCapacity=True)
		return "Terminated"
	except Exception as e:
		#if 'violate group\'s min size constraint' in e.response['Error']['Message']:
		raise e

def replaceAsgInstance(instance_id):
	'''
	input: instance-id
	'''
	asg_client = boto3.client('autoscaling')
	try:
		asg_client.terminate_instance_in_auto_scaling_group(InstanceId=instance_id,ShouldDecrementDesiredCapacity=False)
		return "Terminated"
	except Exception as e:
		#if 'violate group\'s min size constraint' in e['response']['Error']['Message']:
		raise e

# EC2
def getInstanceIP(instance):
	'''
	input instance id
	return: private ip
	'''
	ec2_client = boto3.client('ec2')
	return ec2_client.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]['PrivateIpAddress']


# AWS exception handling: e['response']['Error']['Message']