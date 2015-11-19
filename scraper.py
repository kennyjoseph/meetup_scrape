import requests
from time import sleep
import json
from pymongo import MongoClient
from itertools import izip_longest
from collections import defaultdict
##################################################
##############GLOBALS#############################
##################################################
API_KEY = "YOUR_API_KEY";

RADIUS = 35

PAGE_LIMIT = 200

API = "https://api.meetup.com/2/"

##For now, lets just have a list of the cities we want
##its not hard to scrape all cities, but I really don't want/need that much data
cities = [ ["san_francisco",37.658,-122.287, RADIUS]]
#["pittsburgh",40.440064, -80.000725, RADIUS],
#["buffalo", 42.8950,-78.875, RADIUS]]

error_log = open("error_nyc.txt","w")
##################################################
##############GET REQUESTS########################
##################################################
def print_json(json_data):
	print json.dumps(json_data, sort_keys=True,indent=4, separators=(',', ': '))

def get_from_api(part_of_api, params, processing_function, db, processing_params = None):
	sleep(7)
	params.update({"page": PAGE_LIMIT, "sign":"true", "key": API_KEY})

	#print "Part of api: " + part_of_api
	print "Request: " + API + part_of_api +  " with params:"
	print params


	return_values = []

	try:
		response = defaultdict(str,requests.get(API+part_of_api + ".json",params=params).json())
		return_values = processing_function(response['results'], db, processing_params)

	except:
		error_log.write("FAILED REQUEST: " + part_of_api + " " + str(params))
		error_log.write("f")
		error_log.write("\n")
		print "FAILED REQUEST: " + part_of_api + " " + str(params)
		return []

	while response["meta"]["next"] != "":
		sleep(7)
		print 'NEXT: ' + response["meta"]["next"]
		try:
			response = defaultdict(str,requests.get(response["meta"]["next"]).json())
			return_values += processing_function(response['results'], db, processing_params)
		except :
			error_log.write("FAILED REQUEST: " + part_of_api + " " + str(params))
			error_log.write("f")
			error_log.write("\n")
			print "FAILED REQUEST: " + part_of_api + " " + str(params)
			return []

	if return_values is not None:
		print 'returning: ' + str(len(return_values)) + ' ' + part_of_api
	else:
		return_values = []

	return return_values


def chunker(n, iterable, padvalue=None):
    "chunker(3, 'abcdefg', 'x') --> ('a','b','c'), ('d','e','f'), ('g','x','x')"
    return izip_longest(*[iter(iterable)]*n, fillvalue=padvalue)

##################################################
##############PROCESSING FUNCTIONS################
##################################################

##NOT USED: description
def insert(db_type, val):
	try:
		return db_type.insert(val)
	except Exception as e:
		print str(e)
		error_log.write(str(e))
		error_log.write("\n")
		return None


def groups_processing_function(group_json, db_groups, params):
	#id,name,created,[category][name],city,lat,lon, [organizer][member_id],
	#[name for name in topics], who, join_mode, members, rating,
	#[membership_dues][fee],[membership_dues][fee_desc],[membership_dues][required]
	unwanted_keys = ['group_photo', "link","urlname", "visibility"]
	output = []
	for g in group_json:
		g.update({"_id": g["id"]})
		del g["id"]
		for k in unwanted_keys:
			if k in g:
				del g[k]
		output.append(insert(db_groups,g))
	return [o for o in output if o is not None]

##Members to Groups relation
def group_member_processing_function(member_group_json, db_users_to_groups, params):
	group_id = params["group_id"]
	inserted = [[member_group["id"],insert(db_users_to_groups,
											{"member_id":member_group["id"], 
				  							"group_id":group_id})]
				 for member_group in member_group_json]
	return [mg[0] for mg in inserted if mg[1] is not None]


def group_member_profile_processing_function(group_member_profile_json, db_profiles, params):
	#for answer in answers: member_id,[group][id],comment (if exists!), question_id, question, answer
	inserted = []
	for profile in group_member_profile_json:
		if 'comment' in profile:
			inserted.append(insert(db_profiles,
									{
										"member_id" : profile["member_id"],
										"group_id" : profile["group"]["id"],
										"type" : "COMMENT",
										"question" : "",
										"answer" : profile["comment"]
									})
							)
		if 'answers' in profile:
			for answer in profile["answers"]:
				inserted.append(insert(db_profiles, 
										{
											"member_id" : profile["member_id"],
											"group_id" : profile["group"]["id"],
											"type" : "QA",
											"question" : answer["question"],
											"answer" : answer["answer"]
										})
								)

		inserted.append(insert(db_profiles,profile))

	return [i for i in inserted if i is not None]

def event_processing_function(event_json, db_events, params):
	#id,name,created,time,headcount,maybe_rsvp_count,yes_rsvp_count,waitlist,venue
	#NOT_USED:description(HTML)
	db_venue = params["db_venue"]

	inserted = []
	for event in event_json:
		if "venue" in event:
			venue_id = venue_processing_function(event['id'],event['venue'],db_venue)
			del event["venue"]
		else: 
			venue_id = None
		
		group_id = event["group"]["id"]
		del event["group"]
		event.update({"_id": event["id"], "venue_id":venue_id, "group_id":group_id})
		inserted.append(insert(db_events,event))

	return [i for i in inserted if i is not None]

def venue_processing_function(event_id,venue_json, db_venue):
	#id,lat,lon,zip,city,address_1,name
	venue_json.update({"_id": venue_json["id"], "event_id":event_id})
	del venue_json["id"]
	v = insert(db_venue,venue_json)
	if v is not None:
		return v
	return venue_json["_id"]



def rsvp_processing_function(rsvp_json, db_rsvp, params):
	#rsvp_id,created,response, [member][member_id],[group][id], [event][id], comments,mtime (time modified),
	inserted = []
	for rsvp in rsvp_json:
		rsvp_dict = { 
			"rsvp_id" : rsvp["rsvp_id"],
			"response": rsvp["response"],
			"created" : rsvp["created"],
			"guests" : rsvp["guests"],
			"mod_time" : rsvp["mtime"],
			"event_id": rsvp["event"]["id"],
			"group_id": rsvp["group"]["id"],
			"member_id": rsvp["member"]["member_id"]
		}
		if "comments" in rsvp:
			rsvp_dict["comment"] = rsvp["comments"]

		inserted.append(insert(db_rsvp,rsvp_dict))

	return [i for i in inserted if i is not None]



def member_processing_function(member_json, db_members, params):
	#id,name,joined,lat,lon,name,bio (HTML),city,[name for name in topics],visited
	#NOT USED: photo, other_services,status
	unwanted_keys = ["topics","state","self","photo","other_services","link"]
	inserted = []
	for m in member_json:
		m.update({"_id": m["id"]})
		del m["id"]
		for k in unwanted_keys:
			if k in m:
				del m[k]
		inserted.append(insert(db_members,m))

	return [i for i in inserted if i is not None]



##################################################
##############MAIN################################
##################################################
def scrape_city(city, client):
	#client.drop_database(city[0])
	db = client[city[0]]
	##get groups in the city by lat/lon/radius
	groups = get_from_api("groups", 
						  {"lat":city[1],"lon":city[2],"radius":city[3], "fields":"membership_dues,topics,join_info,other_services"}, 
						  groups_processing_function,
						  db.groups)
	
	groups = db.groups.distinct("_id")
	n_groups = len(groups)
	finished_groups = db.finished_groups.distinct("_id")
	groups = [group for group in groups if group not in finished_groups]

	
	chunker_len =  100

	i = len(finished_groups)
	for group_id in groups:
		print "Group: " + str(i) + " of: " +  str(n_groups)
		i +=1
		print group_id
		##get the members of the group
		members = get_from_api("members", {"group_id":group_id}, 
								group_member_processing_function, 
								db.member_to_group,
								processing_params={"group_id":group_id})

		print "\tNum members: " + str(len(members))
		
		##get the profile of the member for this specific group
		mem_count=0
		for member_chunk in chunker(chunker_len,members):
			print 'Getting profile for member: ' + str(mem_count) + ' of ' + str(len(members))
			mem_count+=chunker_len
			member_ids = ",".join([str(m) for m in member_chunk if m is not None])
			get_from_api("profiles", 
						{"group_id":group_id, "member_id":member_ids}, 
						group_member_profile_processing_function,
						db.group_member_profile)


		##get the events
		events = get_from_api("events", 
							  {"group_id":group_id, "status":"past,upcoming","fields":"event_hosts,comment_count,photo_count,rsvpable,rsvp_rules"}, 
							  event_processing_function, 
							  db.events,
							  processing_params={"db_venue": db.venue})

		print "\tNum events: " + str(len(events))

		##get the RSVPs for each event
		ev_count=0
		for event_chunk in chunker(chunker_len,events):
			print 'Getting rsvps for event: ' + str(ev_count) + ' of ' + str(len(events))
			ev_count+=chunker_len
			event_ids=",".join([str(e) for e in event_chunk if e is not None])
			get_from_api("rsvps", 
						 {"event_id":event_ids}, 
						 rsvp_processing_function,
						 db.rsvps)


		print 'inserting into finished_groups'
		insert(db.finished_groups,{"_id":group_id})
		##Could get comments... not right now though
		##Could get ratings... not right now though

	all_users_in_city = db.member_to_group.distinct("member_id")
	finished_users = db.members.distinct("_id")
	n_users =len(all_users_in_city)

	all_users_in_city = [user for user in all_users_in_city if user not in finished_users]
	
	print 'n city users: ' + str(n_users)
	u_count = len(finished_users)
	for user_chunk in chunker(chunker_len,all_users_in_city):
		print "User: " + str(u_count) + " of: "  + str(n_users)
		u_count+= chunker_len
		member_ids = ",".join([str(u) for u in user_chunk if u is not None])
		get_from_api("members", 
			   		 {"member_id":member_ids}, 
			   		 member_processing_function,
			   		 db.members)
		##could get topics that each user follows, not right now though

client = MongoClient()
for city in cities:
	##Could get comments... not right now though
	##Could get ratings... not right now though
	scrape_city(city, client)
error_log.close()
