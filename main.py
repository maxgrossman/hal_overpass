import openai
import json
import string
import requests
import urllib.parse
import os
import datetime
import osm2geojson

NOMINATIM = os.environ.get('NOMINATIM_URL', "https://nominatim.openstreetmap.org/search.php")
OVERPASS = os.environ.get('OVERPASS_URL', "https://overpass-api.de/api/interpreter")
REQUIRED_TOKENS = ['geospatial_feature', 'place', 'osm_types']

openai.api_key = os.environ.get('OPENAI_API_KEY')

user_input_prompt = string.Template(
"""
Label the geospatial feature, place, and osm types in the following sentence.
Return it in json format, make keys snake case, and return the osm types in a list.
Remember, osm types include nodes, ways, and relations.
One more thing, geospatial features are points of interests, transportation features, or natural features.

$user_input
"""
)

generate_overpass_query_promt = string.Template(
"""
Generate an Overpass API query that will download all $geospatial_feature inside the bbox.
$geospatial_feature can be $osm_types.
Make sure bbox is lowercased and do not surround it with {{}}
"""
)

def get_utc_iso_time():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

# https://stackoverflow.com/a/23794010
def open_mkdir_p(path, mode = 'r'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, mode)

def log_attempt(user_input_completion_prompt="", user_input_tokens={},
                nominatim_response="", overpass_response="", success=True, iso_timestamp=get_utc_iso_time()):
    log_file = os.path.join('telemetry', 'success' if success else 'failure', f"{get_utc_iso_time()}.json")
    with open_mkdir_p(log_file, 'w+') as f:
        f.write(json.dumps({
            "user_input_completion_prompt": user_input_completion_prompt,
            "user_input_tokens": user_input_tokens,
            "nominatim_response": nominatim_response,
            "overpass_response": overpass_response
        }))

def write_output(output_data, output_file):
    with open_mkdir_p(output_file, 'w+') as f:
        f.write(output_data)
        f.close()

def get_overpass_data(user_input):
    iso_timestamp = get_utc_iso_time()
    user_input_completion_prompt = user_input_prompt.substitute({'user_input': user_input})
    user_input_completion = openai.Completion.create(
        engine="text-davinci-003",
        temperature=0.5,
        max_tokens=256,
        prompt=user_input_completion_prompt
    )
    user_input_tokens = None
    try:
        user_input_tokens = json.loads(user_input_completion.choices[0].text)
    except Exception as e:
        log_attempt(user_input_completion_prompt=user_input_completion_prompt, success=False)
        print('failed to parse user input.')
        return

    if not all(token in user_input_tokens for token in REQUIRED_TOKENS) or \
           any(token_value is None for token_value in user_input_tokens.values()):
        print('could not quite figure out what features you wanted, as again.')
        log_attempt(user_input_completion_prompt=user_input_completion_prompt, user_input_tokens=user_input_tokens, \
                    success=False, iso_timestamp=iso_timestamp)
        return

    overpass_query_completion = openai.Completion.create(
        engine="text-davinci-003",
        temperature=0.5,
        max_tokens=256,
        prompt=generate_overpass_query_promt.substitute({
            'geospatial_feature': user_input_tokens['geospatial_feature'],
            'osm_types': " or ".join(user_input_tokens['osm_types']),
            'place': user_input_tokens['place'].title()
        })
    )

    nominatim_data = requests.get(f"{NOMINATIM}?q={user_input_tokens['place']}&polygon_geojson=1&format=jsonv2")

    if nominatim_data.status_code != 200:
        print(f"Nominatim does not know about the place {user_input_tokens['place']}")
        log_attempt(user_input_completion_prompt=user_input_completion_prompt, user_input_tokens=user_input_tokens, \
                    nominatim_response=nominatim_data.text, success=False, iso_timestamp=iso_timestamp)
        return

    place_data = nominatim_data.json()
    place_bounds = place_data[0]['boundingbox']
    place_overpass_bounds = f'{place_bounds[0]},{place_bounds[2]},{place_bounds[1]},{place_bounds[3]}'

    overpass_query = overpass_query_completion.choices[0].text.replace('```','').replace('bbox', place_overpass_bounds)
    overpass_data = requests.post(OVERPASS, data={'data': overpass_query})


    folder_name = f"{user_input_tokens['place']}_{user_input_tokens['geospatial_feature']}_{'|'.join(user_input_tokens['osm_types'])}_{get_utc_iso_time()}"

    query_file_name = os.path.join('results', folder_name, f"{folder_name}.overpass.query")
    write_output(overpass_query, query_file_name)

    if overpass_data.status_code != 200:
        print(f"Overpass could not quite understand the query that built. We wrote it to {query_file_name} where you can have a look yourself.")
        log_attempt(user_input_completion_prompt=user_input_completion_prompt, user_input_tokens=user_input_tokens, \
            nominatim_response=nominatim_data.text, overpass_response=overpass_data.text, success=False, iso_timestamp=iso_timestamp)
        return

    data_file_name = os.path.join('results', folder_name, f"{folder_name}.overpass.geojson")
    overpass_geojson = osm2geojson.json2geojson(overpass_data.text)
    write_output(json.dumps(overpass_geojson), data_file_name)

    log_attempt(user_input_completion_prompt=user_input_completion_prompt, user_input_tokens=user_input_tokens, \
                nominatim_response=nominatim_data.text, overpass_response=overpass_data.text, iso_timestamp=iso_timestamp)

get_overpass_data(input("Ask for data and you will receive: "))
