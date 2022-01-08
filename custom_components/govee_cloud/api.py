import json

import logging
import aiohttp

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
    ret = {}
    if response is not None and 'devices' in response:
        for device in response['devices']:
            device['deviceExt']['lastDeviceData'] = json.loads(device['deviceExt']['lastDeviceData'])
            device['deviceExt']['deviceSettings'] = json.loads(device['deviceExt']['deviceSettings'])
            device['deviceExt']['extResources'] = json.loads(device['deviceExt']['extResources'])
            ret[device['device']] = device
        return ret

    return None


async def request(url, headers=None, data=None):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            return await response.json()
