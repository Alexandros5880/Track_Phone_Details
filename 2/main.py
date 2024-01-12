import phonenumbers
from phonenumbers import geocoder
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from opencage.geocoder import OpenCageGeocode
key = 'ceb00113660c44d4a4d41208236e6b16'
import folium
from folium.features import DivIcon
import webbrowser

# Get all valid numberscan be exist from start numbers
def GetValidNumberPrefixs(results, phonenumber):
  valida_numbers = {}
  for i in COUNTRY_CODE_TO_REGION_CODE.keys():
    try:
      prefix = '+' + str(i)
      number = prefix + phonenumber  
      pepnumber = phonenumbers.parse(number)
      location = geocoder.description_for_number(pepnumber, "en")
      if len(location) > 0:
        valida_numbers[location] = number
    except KeyError:
      pass
    except:
      pass
  results[phonenumber] = valida_numbers

# Flat dict with numbers to an array with dict{'country_name', 'valid_number'}
def FlatDict(valid_numbers, data):
  for k,v in data.items():
    if type(v) == dict:
      FlatDict(valid_numbers, v)
    else:
      d = {'country': k, 'number': v}
      valid_numbers.append(d)

# Render phones on map
def PointOnMap(valid_numbers):
  myMap = folium.Map(zoom_start=9)
  html_text = "<h3 align=\"center\" style=\"font-size:11px\"><b>"
  for item in valid_numbers:
    pepnumber = phonenumbers.parse(item['number'])
    location = geocoder.description_for_number(pepnumber, "en")
    opencagegeocoder = OpenCageGeocode(key)
    query = str(location)
    results = opencagegeocoder.geocode(query)
    lat = results[0]['geometry']['lat']
    lng = results[0]['geometry']['lng']
    point_text = "{}, {}, {}N, {}E".format(item['number'], location, lat, lng)
    html_text += point_text + "<br/>"
    folium.Marker(
      [lat, lng],
      popup=point_text
    ).add_to(myMap)
  html_text += "</br></h3>"
  myMap.get_root().html.add_child(folium.Element(html_text))
  myMap.save("phones_location.html")
  webbrowser.open("phones_location.html")






search_numbers = ['21079352015', '21079393770']

results_numbers = {}
for n in search_numbers:
  GetValidNumberPrefixs(results_numbers, n)

valid_numbers = []
FlatDict(valid_numbers, results_numbers)

PointOnMap(valid_numbers)