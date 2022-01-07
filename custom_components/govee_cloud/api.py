import json

import requests
import logging

CLIENT_ID = 'b529ce1f1bd14ff29120b697bd308aa5'

_LOGGER = logging.getLogger(__name__)

async def get_access_token(email, password):
    response = await request(
        'https://app2.govee.com/account/rest/account/v1/login',
        {"Content-Type": "application/json"},
        {"email": email, "client": CLIENT_ID, "password": password, }
    )
    if response is not None and 'client' in response:
        return response['client']['token']
    _LOGGER.error('Govee Cloud: Failed to get access token for user: ' + email + '. Response: ' + str(response))
    return None


async def get_devices(access_token):
    response = await request(
        'https://app2.govee.com/device/rest/devices/v1/list',
        {
            'Authorization': 'Bearer ' + access_token,
            'Appversion': '4.7.0',
            "Content-Type": "application/json",
            'clientId': CLIENT_ID,
            'clientType': "1",
            'iotVersion': "0"
        }
    )

    if response is not None and 'devices' in response:
        for device in response['devices']:
            device['deviceExt']['lastDeviceData'] = json.loads(device['deviceExt']['lastDeviceData'])
            device['deviceExt']['deviceSettings'] = json.loads(device['deviceExt']['deviceSettings'])
            device['deviceExt']['extResources'] = json.loads(device['deviceExt']['extResources'])
        return response['devices']

    return None


async def request(url, headers=None, data=None):
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        _LOGGER.error('Govee Cloud: HTTP error: ' + str(http_err))
    except Exception as err:
        _LOGGER.error('Govee Cloud: Other error: ' + str(err))
    return None

#
# import asyncio
#
#
# async def a():
#     print(await get_devices(
#         'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InNpZCI6ImZNWXNFZDMyYVNiSnFrbFY3dWtUTVdJbmNnazVWaXdYIn0sImlhdCI6MTY0MTQ4NDY2NywiZXhwIjoxNjQ2NjY4NjY3fQ.i6blEid0SnHAO35X9xt0vYQ0qUbD9Dpb0iwV2UPLquc')
#           )
#
#
# # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InNpZCI6ImZNWXNFZDMyYVNiSnFrbFY3dWtUTVdJbmNnazVWaXdYIn0sImlhdCI6MTY0MTQ4NDY2NywiZXhwIjoxNjQ2NjY4NjY3fQ.i6blEid0SnHAO35X9xt0vYQ0qUbD9Dpb0iwV2UPLquc
#
# asyncio.run(a())
