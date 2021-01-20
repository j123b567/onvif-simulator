from flask import Flask, Response, request
import xml.etree.ElementTree as ET
import datetime
import uuid

app = Flask(__name__)

SOAP_HEADER_TAG = '{http://www.w3.org/2003/05/soap-envelope}Header'
SOAP_BODY_TAG = '{http://www.w3.org/2003/05/soap-envelope}Body'

SOAP_MUST_UNDERSTAND_ATTR = '{http://www.w3.org/2003/05/soap-envelope}mustUnderstand'

ADDRESSING_ACTION_TAG = '{http://www.w3.org/2005/08/addressing}Action'
ADDRESSING_MESSAGE_ID_TAG = '{http://www.w3.org/2005/08/addressing}MessageID'
ADDRESSING_REPLY_TO_TAG = '{http://www.w3.org/2005/08/addressing}ReplyTo'
ADDRESSING_ADDRESS_TAG = '{http://www.w3.org/2005/08/addressing}Address'

DS_GET_SYSTEM_DATE_AND_TIME_RESPONSE_TAG = '{http://www.onvif.org/ver10/device/wsdl}GetSystemDateAndTimeResponse'
DS_SYSTEM_DATE_AND_TIME_TAG = '{http://www.onvif.org/ver10/device/wsdl}SystemDateAndTime'

DS_GET_SERVICES_TAG = '{http://www.onvif.org/ver10/device/wsdl}GetServices'
DS_INCLUDE_CAPABILITY = '{http://www.onvif.org/ver10/device/wsdl}IncludeCapability'


def _get_action(root):
    header = root.find(SOAP_HEADER_TAG)
    action = header.find(ADDRESSING_ACTION_TAG)
    return action.text


def _parse_qname(qname):
    if qname[:1] == "{":
        return qname[1:].rsplit("}", 1)
    else:
        return None, qname


class WsdlQueryHeader:
    def __init__(self, header, body=None):
        action = header.find(ADDRESSING_ACTION_TAG)
        if action is None and body is not None:
            self.action = '/'.join(_parse_qname(body[0].tag))
        else:
            self.action = action.text
        message_id = header.find(ADDRESSING_MESSAGE_ID_TAG)
        if message_id is not None:
            self.message_id = message_id.text
        else:
            self.message_id = None


def ver10_device_factory(action, body_el):
    if action == 'http://www.onvif.org/ver10/device/wsdl/GetSystemDateAndTime':
        return GetSystemDateAndTime(body_el)
    elif action == 'http://www.onvif.org/ver10/device/wsdl/GetServices':
        return GetServices(body_el)
    else:
        return Debug(action, body_el)


def ver10_media_factory(action, body_el):
    if action == 'http://www.onvif.org/ver10/media/wsdl/GetProfiles':
        return GetProfiles(body_el)
    else:
        return Debug(action, body_el)


def ver20_ptz_factory(action, body_el):
    if action == 'http://www.onvif.org/ver20/ptz/wsdl/GetPresets':
        return GetPresets(body_el)
    elif action == 'http://www.onvif.org/ver20/ptz/wsdl/GotoPreset':
        return GotoPreset(body_el)
    else:
        return Debug(action, body_el)


class WsdlQuery:
    def __init__(self, data):
        root = ET.fromstring(data)
        header = root.find(SOAP_HEADER_TAG)
        body = root.find(SOAP_BODY_TAG)

        self.header = WsdlQueryHeader(header, body)

        self.body_el = body

        security_el = header.find("{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security")
        if security_el:
            username_token_el = security_el.find("{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}UsernameToken")
            username_el = username_token_el.find("{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Username")
            app.logger.info("WsdlQuery(username={})".format(username_el.text))


class Debug:
    def __init__(self, action, body):
        self.action = action
        self.body = body

    def query(self):
        app.logger.critical('Unknown action: {}'.format(self.action))
        for el in self.body.iter():
            app.logger.critical('\t{}'.format(el))


class GetSystemDateAndTime:
    def __init__(self, body):
        pass

    def query(self):
        app.logger.info(self.__class__.__name__)
        ns = {'tt': 'http://www.onvif.org/ver10/schema'}

        tree = ET.parse('GetSystemDateAndTime.xml')
        root = tree.getroot()
        body_el = root.find(SOAP_BODY_TAG)
        response = body_el.find(DS_GET_SYSTEM_DATE_AND_TIME_RESPONSE_TAG)
        system_date_and_time_el = response.find(DS_SYSTEM_DATE_AND_TIME_TAG)

        now = datetime.datetime.utcnow()

        system_date_and_time_el.find('tt:DaylightSavings', ns).text = 'false'
        system_date_and_time_el.find('tt:TimeZone/tt:TZ', ns).text = 'UTC'

        def set_date_time(el, ts):
            time_el = el.find('tt:Time', ns)
            time_el.find('tt:Hour', ns).text = str(ts.time().hour)
            time_el.find('tt:Minute', ns).text = str(ts.time().minute)
            time_el.find('tt:Second', ns).text = str(ts.time().second)
            date_el = el.find('tt:Date', ns)
            date_el.find('tt:Year', ns).text = str(ts.date().year)
            date_el.find('tt:Month', ns).text = str(ts.date().month)
            date_el.find('tt:Day', ns).text = str(ts.date().day)

        utc_date_time_el = system_date_and_time_el.find('tt:UTCDateTime', ns)
        set_date_time(utc_date_time_el, now)

        local_date_time_el = system_date_and_time_el.find('tt:LocalDateTime', ns)
        set_date_time(local_date_time_el, now)

        return root


class GetServices:
    def __init__(self, body):
        get_services_el = body.find(DS_GET_SERVICES_TAG)
        include_capability_el = get_services_el.find(DS_INCLUDE_CAPABILITY)
        self.include_capability = include_capability_el.text.lower() == 'true'

    def query(self):
        app.logger.info("{}(include_capability={})".format(self.__class__.__name__, self.include_capability))

        tree = ET.parse('GetServices.xml')
        root = tree.getroot()
        return root


class GetProfiles:
    def __init__(self, body):
        pass

    def query(self):
        app.logger.info(self.__class__.__name__)

        tree = ET.parse('GetProfiles.xml')
        root = tree.getroot()
        return root


class GetPresets:
    def __init__(self, body):
        ns = {'tptz': 'http://www.onvif.org/ver20/ptz/wsdl'}
        self.profile = body.find('tptz:GetPresets/tptz:ProfileToken', ns).text

    def query(self):
        app.logger.info('{}(profile={})'.format(self.__class__.__name__, self.profile))

        tree = ET.parse('GetPresets.xml')
        root = tree.getroot()
        return root


class GotoPreset:
    def __init__(self, body):
        ns = {'tptz': 'http://www.onvif.org/ver20/ptz/wsdl'}
        self.profile = body.find('tptz:GotoPreset/tptz:ProfileToken', ns).text
        self.preset = body.find('tptz:GotoPreset/tptz:PresetToken', ns).text
        self.speed = body.find('tptz:GotoPreset/tptz:Speed', ns).text

    def query(self):
        app.logger.info('{}(profile={}, preset={}, speed={})'.format(
            self.__class__.__name__,
            self.profile,
            self.preset,
            self.speed))

        tree = ET.parse('GotoPreset.xml')
        root = tree.getroot()
        return root


def _ensure_element(parent, name):
    el = parent.find(name)
    if el is None:
        el = ET.SubElement(parent, name)
    return el


def _compose_response(data, action=None, message_id=None):
    header_el = _ensure_element(data, SOAP_HEADER_TAG)

    if message_id is not None:
        message_id_el = _ensure_element(header_el, ADDRESSING_MESSAGE_ID_TAG)
        message_id_el.text = message_id

    if action is not None:
        action_el = _ensure_element(header_el, ADDRESSING_ACTION_TAG)
        action_el.attrib[SOAP_MUST_UNDERSTAND_ATTR] = 'true'
        action_el.text = action

    reply_to_el = _ensure_element(header_el, ADDRESSING_REPLY_TO_TAG)
    reply_to_el.attrib[SOAP_MUST_UNDERSTAND_ATTR] = 'true'

    address_el = _ensure_element(reply_to_el, ADDRESSING_ADDRESS_TAG)
    address_el.text = 'http://www.w3.org/2005/08/addressing/anonymous'

    resp = Response(ET.tostring(data, encoding='utf8', method='xml'))
    resp.headers['Content-Type'] = 'application/soap+xml; charset=utf-8; action="{}"'.format(action)
    return resp


@app.route('/onvif/device_service', methods=['POST'])
def device_service():
    wsdl = WsdlQuery(request.data)
    response_data = ver10_device_factory(wsdl.header.action, wsdl.body_el).query()
    return _compose_response(response_data, wsdl.header.action, wsdl.header.message_id)


@app.route('/onvif/media_service', methods=['POST'])
def media_service():
    wsdl = WsdlQuery(request.data)
    response_data = ver10_media_factory(wsdl.header.action, wsdl.body_el).query()
    return _compose_response(response_data, wsdl.header.action, wsdl.header.message_id)


@app.route('/onvif/ptz_service', methods=['POST'])
def ptz_service():
    wsdl = WsdlQuery(request.data)
    response_data = ver20_ptz_factory(wsdl.header.action, wsdl.body_el).query()
    return _compose_response(response_data, wsdl.header.action, wsdl.header.message_id)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
