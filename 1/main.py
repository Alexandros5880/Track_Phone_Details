import phonenumbers
import opencage
import folium
from myphone import number
from phonenumbers import geocoder

pepnumber = phonenumbers.parse(number)
location = geocoder.description_for_number(pepnumber, "en")
print("Phone Country: ", location)

from phonenumbers import carrier
service_pro = phonenumbers.parse(number)
print("Phone Compoany: ", carrier.name_for_number(service_pro, "en"))

from opencage.geocoder import OpenCageGeocode
key = 'ceb00113660c44d4a4d41208236e6b16'
geocoder = OpenCageGeocode(key)
query = str(location)
results = geocoder.geocode(query)
#print(results)

lat = results[0]['geometry']['lat']
lng = results[0]['geometry']['lng']
print(lat,lng)

myMap = folium.Map(location=[lat, lng], zoom_start=0)
folium.Marker([lat, lng], popup=location).add_to(myMap)
myMap.save("results/phonelocation.html")