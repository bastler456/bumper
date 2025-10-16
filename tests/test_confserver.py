import mock
import bumper
import asyncio
import pytest
import os
import json
import tinydb
import pytest_aiohttp
import pytest_asyncio
import datetime, time
from aiohttp import web
import logging
from testfixtures import LogCapture
from unittest.mock import MagicMock
import subprocess
import socket


def wait_for_mqtt(host: str, port: int, timeout: int = 10):
    """Wait for the MQTT broker to be available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"MQTT broker not available at {host}:{port}")


@pytest.fixture(scope="session")
def mosquitto_container():
    """Start Mosquitto using docker-compose before tests, stop after."""
    subprocess.run(["docker", "compose", "up", "-d", "mosquitto"], check=True)

    try:
        wait_for_mqtt("localhost", 1883)
    except TimeoutError:
        subprocess.run(["docker-compose", "logs", "mosquitto"])
        raise

    yield

    subprocess.run(["docker", "compose", "down"], check=True)


@pytest.fixture()
def certs() -> dict:
    certs: dict = {"CA_CERT": "certs/ca.crt",
                   "CLIENT_CERT": "certs/bumper.crt",
                   "CLIENT_KEY": "certs/bumper.key"}
    return certs


def create_confserver():
    return bumper.ConfServer("127.0.0.1:11111", False)


def create_app(certs: dict = None):
    confserver = bumper.ConfServer("127.0.0.1:11111", False)
    confserver.confserver_app(certs)
    return confserver.app


def async_return(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


def remove_existing_db():
    if os.path.exists("tests/tmp.db"):
        os.remove("tests/tmp.db")  # Remove existing db


@pytest.mark.asyncio
async def test_confserver_ssl(certs, mosquitto_container):
    conf_server = bumper.ConfServer(("127.0.0.1", 111111), usessl=True)
    conf_server.confserver_app(certs)
    asyncio.create_task(conf_server.start_server())


@pytest.mark.asyncio
async def test_confserver_exceptions(certs, mosquitto_container):
    with LogCapture() as l:

            conf_server = bumper.ConfServer(("127.0.0.1", 8007), usessl=True)
            conf_server.confserver_app(certs)      
            conf_server.site = web.TCPSite

            #bind permission       
            conf_server.site.start = mock.Mock(side_effect=OSError(1, "error while attempting to bind on address ('127.0.0.1', 8007): permission denied"))
            await conf_server.start_server()

            #asyncio Cancel
            conf_server.site = web.TCPSite
            conf_server.site.start = mock.Mock(side_effect=asyncio.CancelledError)
            await conf_server.start_server()

            #general exception
            conf_server.site = web.TCPSite
            conf_server.site.start = mock.Mock(side_effect=Exception(1, "general"))
            await conf_server.start_server()

    l.check_present(
        ("confserver", "ERROR", "error while attempting to bind on address ('127.0.0.1', 8007): permission denied")
    )


@pytest.mark.asyncio
async def test_confserver_no_ssl(mosquitto_container):
    conf_server = bumper.ConfServer(("127.0.0.1", 111111), usessl=False)
    conf_server.confserver_app()
    asyncio.create_task(conf_server.start_server())


@pytest.mark.asyncio
async def test_confserver_no_certs_provided(mosquitto_container):
    conf_server = bumper.ConfServer(("127.0.0.1", 111111), usessl=True)
    with pytest.raises(TypeError):
        conf_server.confserver_app()


def test_get_milli_time():
    cserv = create_confserver()
    assert (
        cserv.get_milli_time(
            datetime.datetime(
                2018, 1, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp()
        )
        == 1514768400000
    )


@pytest.mark.asyncio
async def test_base(aiohttp_client, certs, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing

    # Start XMPP
    xmpp_address = ("127.0.0.1", 5223)
    xmpp_server = bumper.XMPPServer(xmpp_address)
    bumper.xmpp_server = xmpp_server
    await xmpp_server.start_async_server()

    client = await aiohttp_client(create_app())
    resp = await client.get("/")
    assert resp.status == 200   

    bumper.xmpp_server.disconnect()


@pytest.mark.asyncio
async def test_restartService(aiohttp_client, certs, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing

    # Start XMPP
    xmpp_address = ("127.0.0.1", 5223)
    xmpp_server = bumper.XMPPServer(xmpp_address)
    bumper.xmpp_server = xmpp_server
    await xmpp_server.start_async_server()

    client = await aiohttp_client(create_app())

    resp = await client.get("/restart_Helperbot")
    assert resp.status == 200

    resp = await client.get("/restart_XMPPServer")
    assert resp.status == 200

    xmpp_server.disconnect()


@pytest.mark.asyncio
async def test_RemoveBot(aiohttp_client, mosquitto_container):
    client = await aiohttp_client(create_app())
    resp = await client.get("/bot/remove/test_did")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_RemoveClient(aiohttp_client, mosquitto_container):
    client = await aiohttp_client(create_app())
    resp = await client.get("/client/remove/test_resource")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_login(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test without user
    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/user/login")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing 

    # Test global_e without user
    resp = await client.get("/v1/private/us/en/dev_1234/global_e/1/0/0/user/login")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Add a user to db and test with existing users
    bumper.user_add("testuser")
    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/user/login")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Add a bot to db that will be added to user
    bumper.bot_add("sn_123", "did_123", "dev_123", "res_123", "com_123")
    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/user/login")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Add a bot to db that doesn't have a did
    newbot = {
            "class": "dev_1234",
            "company": "com_123",
            # "did": self.did,
            "name": "sn_1234",            
            "resource": "res_1234",            
    }
    bumper.bot_full_upsert(newbot)

    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/user/login")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]


@pytest.mark.asyncio
async def test_logout(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Add a token to user and test
    bumper.user_add("testuser")
    bumper.user_add_device("testuser", "dev_1234")
    bumper.user_add_token("testuser", "token_1234")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/logout?accessToken={}".format(
            "token_1234"
        )
    )

    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_checkLogin(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test without token
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/checkLogin?accessToken={}".format(
            None
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert jsonresp["data"]["accessToken"] != "token_1234"
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Add a user to db and test with existing users
    bumper.user_add("testuser")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/checkLogin?accessToken={}".format(
            None
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert jsonresp["data"]["accessToken"] != "token_1234"
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Test again using global_e app
    bumper.user_add("testuser")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/user/checkLogin?accessToken={}".format(
            None
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert jsonresp["data"]["accessToken"] != "token_1234"
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Remove dev from tmpuser
    bumper.user_remove_device("tmpuser", "dev_1234")

    # Add a token to user and test
    bumper.user_add("testuser")
    bumper.user_add_device("testuser", "dev_1234")
    bumper.user_add_token("testuser", "token_1234")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/checkLogin?accessToken={}".format(
            "token_1234"
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert jsonresp["data"]["accessToken"] == "token_1234"
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]

    # Test again using global_e app
    bumper.user_add("testuser")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/user/checkLogin?accessToken={}".format(
            "token_1234"
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "accessToken" in jsonresp["data"]
    assert jsonresp["data"]["accessToken"] == "token_1234"
    assert "uid" in jsonresp["data"]
    assert "username" in jsonresp["data"]


@pytest.mark.asyncio
async def test_getAuthCode(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test without user or token
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/getAuthCode?uid={}&accessToken={}".format(
            None, None
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.ERR_TOKEN_INVALID

    # Test as global_e
    resp = await client.get(
        "/v1/global/auth/getAuthCode?uid={}&deviceId={}".format(None, "dev_1234")
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.ERR_TOKEN_INVALID

    # Add a token to user and test
    bumper.user_add("testuser")
    bumper.user_add_device("testuser", "dev_1234")
    bumper.user_add_token("testuser", "token_1234")
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/getAuthCode?uid={}&accessToken={}".format(
            "testuser", "token_1234"
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "authCode" in jsonresp["data"]
    assert "ecovacsUid" in jsonresp["data"]

    # The above should have added an authcode to token, try again to test with existing authcode
    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/user/getAuthCode?uid={}&accessToken={}".format(
            "testuser", "token_1234"
        )
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS
    assert "authCode" in jsonresp["data"]
    assert "ecovacsUid" in jsonresp["data"]


@pytest.mark.asyncio
async def test_checkAgreement(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/user/checkAgreement")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS

    # Test as global_e
    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/user/checkAgreement"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_homePageAlert(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/ios/1/0/0/campaign/homePageAlert"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_checkVersion(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get("/v1/private/us/en/dev_1234/ios/1/0/0/common/checkVersion")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_checkAppVersion(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/common/checkAPPVersion"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_uploadDeviceInfo(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/common/uploadDeviceInfo"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_getAdByPositionType(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/ad/getAdByPositionType"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_getBootScreen(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/ad/getBootScreen"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_hasUnreadMsg(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/message/hasUnreadMsg"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_getMsgList(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/message/getMsgList"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_getSystemReminder(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/common/getSystemReminder"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_getCnWapShopConfig(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/shop/getCnWapShopConfig"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


@pytest.mark.asyncio
async def test_neng_hasUnreadMessage(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "ecoglobe",
            "token": "us_token",
            "userid": "user123",
            "with": "users",
        },
        "count": 20,
    }
    resp = await client.post("/api/neng/message/hasUnreadMsg", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == 0


@pytest.mark.asyncio
async def test_getProductIotMap(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.post("/api/pim/product/getProductIotMap")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == bumper.RETURN_API_SUCCESS


    # Test getPimFile
    resp = await client.get("/api/pim/file/get/123")
    assert resp.status == 200
    

@pytest.mark.asyncio
async def test_getUsersAPI(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    resp = await client.get("/api/users/user.do")
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "fail"


@pytest.mark.asyncio
async def test_getUserAccountInfo(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    bumper.user_add("testuser")
    bumper.user_add_device("testuser", "dev_1234")
    bumper.user_add_token("testuser", "token_1234")
    bumper.user_add_authcode("testuser", "token_1234", "auth_1234")
    bumper.user_add_bot("testuser", "did_1234")
    bumper.bot_add("sn_1234", "did_1234", "class_1234", "res_1234", "com_1234")

    client = await aiohttp_client(create_app())

    resp = await client.get(
        "/v1/private/us/en/dev_1234/global_e/1/0/0/user/getUserAccountInfo"
    )
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["code"] == "0000"
    assert jsonresp["msg"] == "操作成功"
    assert jsonresp["data"]["userName"] == "fusername_testuser"


@pytest.mark.asyncio
async def test_postUsersAPI(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test FindBest
    postbody = {"todo": "FindBest", "service": "EcoMsgNew"}
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test EcoUpdate
    postbody = {"todo": "FindBest", "service": "EcoUpdate"}
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test loginByItToken - Uses the authcode
    bumper.user_add("testuser")
    bumper.user_add_device("testuser", "dev_1234")
    bumper.user_add_token("testuser", "token_1234")
    bumper.user_add_authcode("testuser", "token_1234", "auth_1234")
    bumper.user_add_bot("testuser", "did_1234")
    bumper.bot_add("sn_1234", "did_1234", "class_1234", "res_1234", "com_1234")
    # Test
    postbody = {
        "country": "US",
        "last": "",
        "realm": "ecouser.net",
        "resource": "dev_1234",
        "todo": "loginByItToken",
        "token": "auth_1234",
        "userId": "testuser",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test as EcoVacs Home (global_e)
    postbody = {
        "country": "US",
        "edition": "ECOGLOBLE",
        "last": "",
        "org": "ECOWW",
        "resource": "dev_1234",
        "todo": "loginByItToken",
        "token": "auth_1234",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test as EcoVacs Home (global_e) & Post Form
    postbody = {
        "country": "US",
        "edition": "ECOGLOBLE",
        "last": "",
        "org": "ECOWW",
        "resource": "dev_1234",
        "todo": "loginByItToken",
        "token": "auth_1234",
    }
    resp = await client.post("/api/users/user.do", data=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test GetDeviceList
    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "dev_1234",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "todo": "GetDeviceList",
        "userid": "testuser",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test SetDeviceNick
    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "dev_1234",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "todo": "SetDeviceNick",
        "nick": "botnick",
        "did": "did_1234",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test AddOneDevice - Same as set nick for some bots
    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "dev_1234",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "todo": "AddOneDevice",
        "nick": "botnick",
        "did": "did_1234",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"

    # Test DeleteOneDevice - remove bot
    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "dev_1234",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "todo": "DeleteOneDevice",
        "did": "did_1234",
    }
    resp = await client.post("/api/users/user.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["result"] == "ok"


@pytest.mark.asyncio
async def test_appsvr_api(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test GetGlobalDeviceList
    postbody = {
        "aliliving": False,
        "appVer": "1.1.6",
        "auth": {
            "realm": "ecouser.net",
            "resource": "ECOGLOBLEac5ae987",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "channel": "google_play",
        "defaultLang": "en",
        "lang": "en",
        "platform": "Android",
        "todo": "GetGlobalDeviceList",
        "userid": "testuser",
    }
    resp = await client.post("/api/appsvr/app.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["ret"] == "ok"

    bumper.bot_add("sn_1234", "did_1234", "ls1ok3", "res_1234", "eco-ng")

    # Test again with bot added
    resp = await client.post("/api/appsvr/app.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["ret"] == "ok"


@pytest.mark.asyncio
async def test_lg_logs(aiohttp_client, certs, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    bumper.bot_add("sn_1234", "did_1234", "ls1ok3", "res_1234", "eco-ng")
    bumper.bot_set_mqtt("did_1234", True)
    confserver = create_confserver()
    client = await aiohttp_client(create_app())

    mqtt_client_1: bumper.MqttClient = confserver.get_mqtt_server()

    # Test return get status
    command_getstatus_resp = {
        "id": "resp_1234",
        "resp": "<ctl ret='ok' status='idle'/>",
        "ret": "ok",
    }
    mqtt_client_1.get_received_messages = mock.MagicMock(
        return_value=(command_getstatus_resp)
    )

    # Test GetGlobalDeviceList
    postbody = {
        "auth": {
            "realm": "ecouser.net",
            "resource": "ECOGLOBLEac5ae987",
            "token": "token_1234",
            "userid": "testuser",
            "with": "users",
        },
        "did": "did_1234",
        "resource": "res_1234",
        "td": "GetCleanLogs",
    }
    resp = await client.post("/api/lg/log.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    jsonresp = json.loads(text)
    assert jsonresp["ret"] == "ok"


@pytest.mark.asyncio
async def test_postLookup(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test FindBest
    postbody = {"todo": "FindBest", "service": "EcoMsgNew"}
    resp = await client.post("/lookup.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["result"] == "ok"

    # Test EcoUpdate
    postbody = {"todo": "FindBest", "service": "EcoUpdate"}
    resp = await client.post("/lookup.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["result"] == "ok"


@pytest.mark.asyncio
async def test_devmgr(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    client = await aiohttp_client(create_app())

    # Test PollSCResult
    postbody = {"td": "PollSCResult"}
    resp = await client.post("/api/iot/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"

    # Test HasUnreadMsg
    postbody = {"td": "HasUnreadMsg"}
    resp = await client.post("/api/iot/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"
    assert test_resp["unRead"] == False

    # Test BotCommand
    bumper.bot_add("sn_1234", "did_1234", "dev_1234", "res_1234", "eco-ng")
    bumper.bot_set_mqtt("did_1234", True)
    postbody = {"toId": "did_1234"}

    # Test return get status
    command_getstatus_resp = {
        "id": "resp_1234",
        "resp": "<ctl ret='ok' status='idle'/>",
        "ret": "ok",
    }
    bumper.mqtt_helperbot.send_command = mock.MagicMock(
        return_value=async_return(command_getstatus_resp)
    )
    resp = await client.post("/api/iot/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"

    # Test return fail timeout
    command_timeout_resp = {"id": "resp_1234", "errno": "timeout", "ret": "fail"}
    bumper.mqtt_helperbot.send_command = mock.MagicMock(
        return_value=async_return(command_timeout_resp)
    )
    resp = await client.post("/api/iot/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "fail"


@pytest.mark.asyncio
async def test_dim_devmanager(aiohttp_client, mosquitto_container):
    remove_existing_db()
    bumper.db = "tests/tmp.db"  # Set db location for testing
    confserver = create_confserver()
    client = await aiohttp_client(create_app())
    bumper.mqtt_helperbot = bumper.mqttserver.MQTTHelperBot("127.0.0.1")

    # Test PollSCResult
    postbody = {"td": "PollSCResult"}
    resp = await client.post("/api/dim/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"

    # Test HasUnreadMsg
    postbody = {"td": "HasUnreadMsg"}
    resp = await client.post("/api/dim/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"
    assert test_resp["unRead"] == False

    # Test BotCommand
    bumper.bot_add("sn_1234", "did_1234", "dev_1234", "res_1234", "eco-ng")
    bumper.bot_set_mqtt("did_1234", True)
    postbody = {"toId": "did_1234"}

    # Test return get status
    command_getstatus_resp = {
        "id": "resp_1234",
        "resp": "<ctl ret='ok' status='idle'/>",
        "ret": "ok",
    }
    bumper.mqtt_helperbot.send_command = mock.MagicMock(
        return_value=async_return(command_getstatus_resp)
    )
    resp = await client.post("/api/dim/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "ok"

    # Test return fail timeout
    command_timeout_resp = {"id": "resp_1234", "errno": "timeout", "ret": "fail"}
    bumper.mqtt_helperbot.send_command = mock.MagicMock(
        return_value=async_return(command_timeout_resp)
    )
    resp = await client.post("/api/dim/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "fail"
    assert test_resp["errno"] == "timeout"

    # Set bot not on mqtt
    bumper.bot_set_mqtt("did_1234", False)
    bumper.mqtt_helperbot.send_command = mock.MagicMock(
        return_value=async_return(command_getstatus_resp)
    )
    resp = await client.post("/api/dim/devmanager.do", json=postbody)
    assert resp.status == 200
    text = await resp.text()
    test_resp = json.loads(text)
    assert test_resp["ret"] == "fail"
