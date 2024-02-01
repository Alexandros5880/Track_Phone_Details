import phonenumbers
from phonenumbers import carrier
from phonenumbers import geocoder
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from opencage.geocoder import OpenCageGeocode
key = 'ceb00113660c44d4a4d41208236e6b16'
import folium
from folium.features import DivIcon
import webbrowser
from twilio.rest import Client
import click

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

#  Get Phones Companies
def get_company_from_twilio(phone_number):
    # Your Twilio Account SID and Auth Token
    account_sid = 'xxx'
    auth_token = 'xxx'
    client = Client(account_sid, auth_token)
    try:
        number_info = client.lookups.phone_numbers(phone_number).fetch(type='carrier')
        company_name = number_info.carrier['name']
        return company_name
    except Exception as e:
        Print(f"\nError: {str(e)}")
        return None

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
    point_text = "{}, {}, {}, {}N, {}E".format(item['number'], location, item['company'], lat, lng)
    html_text += point_text + "<br/>"
    folium.Marker(
      [lat, lng],
      popup=point_text
    ).add_to(myMap)
  html_text += "</br></h3>"
  myMap.get_root().html.add_child(folium.Element(html_text))
  myMap.save("phones_location.html")
  webbrowser.open("phones_location.html")


@click.command()
@click.option('-n', '--number', type=str, help='Specify the phone number')
def main(number):
    search_numbers = [number]

    results_numbers = {}
    for n in search_numbers:
        GetValidNumberPrefixs(results_numbers, n)

    valid_numbers = []
    FlatDict(valid_numbers, results_numbers)
    
    for number_dict in valid_numbers:
        caller_company = get_company_from_twilio(number_dict['number'])
        number_dict['company'] = caller_company
    
    for number_dict in valid_numbers:
        print(f"\n{number_dict}")

    PointOnMap(valid_numbers)


if __name__=="__main__":
    main()
    