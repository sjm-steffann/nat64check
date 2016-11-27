def http_code_data(code, error=False, timeout=False):
    if code == 0:
        if timeout:
            return {
                'status_class': 'bad-score',
                'status_text': 'Client timeout',
                'status_code': 'Client timeout',
            }
        elif error:
            return {
                'status_class': 'bad-score',
                'status_text': 'Client error',
                'status_code': 'Client error',
            }
        else:
            return {
                'status_class': 'bad-score',
                'status_text': 'No result',
                'status_code': 'No result',
            }

    if code is None:
        return {
            'status_class': 'gray',
            'status_text': '-',
            'status_code': '-',
        }

    out = {
        'status_class': '',
        'status_text': 'HTTP {}'.format(code),
        'status_code': 'HTTP {}'.format(code),
    }

    if (200 <= code < 300) or code == 304:
        out['status_class'] = 'good-score'

        if code == 200:
            out['status_text'] = 'Ok'
        elif code == 201:
            out['status_text'] = 'Created'
        elif code == 202:
            out['status_text'] = 'Accepted'
        elif code == 203:
            out['status_text'] = 'Ok (proxy)'
        elif code == 204:
            out['status_text'] = 'Empty'
        elif code == 205:
            out['status_text'] = 'Reset'
        elif code == 206:
            out['status_text'] = 'Partial'
        elif code == 304:
            out['status_text'] = 'Not modified'

    elif 300 <= code < 400:
        out['status_class'] = 'mediocre-score'

        if code == 300:
            out['status_text'] = 'Multiple'
        elif code == 301:
            out['status_text'] = 'Moved'
        elif code == 302:
            out['status_text'] = 'Found'
        elif code == 303:
            out['status_text'] = 'See other'
        elif code == 307:
            out['status_text'] = 'Temporary'
        elif code == 308:
            out['status_text'] = 'Permanent'

    elif code >= 400:
        out['class'] = 'bad-score'

        if code == 400:
            out['status_text'] = 'Bad request'
        elif code == 401:
            out['status_text'] = 'Unauthorized'
        elif code == 402:
            out['status_text'] = 'Payment req.'
        elif code == 403:
            out['status_text'] = 'Forbidden'
        elif code == 404:
            out['status_text'] = 'Not found'
        elif code == 405:
            out['status_text'] = 'Bad method'
        elif code == 406:
            out['status_text'] = 'Not acceptable'
        elif code == 408:
            out['status_text'] = 'Timeout'
        elif code == 409:
            out['status_text'] = 'Conflict'
        elif code == 410:
            out['status_text'] = 'Gone'
        elif code == 426:
            out['status_text'] = 'Upgrade'
        elif code == 429:
            out['status_text'] = 'Rate-limit'
        elif code == 500:
            out['status_text'] = 'Server error'
        elif code == 501:
            out['status_text'] = 'Not implemented'
        elif code == 502:
            out['status_text'] = 'Bad gateway'
        elif code == 503:
            out['status_text'] = 'Unavailable'
        elif code == 504:
            out['status_text'] = 'Proxy timeout'
        elif code == 505:
            out['status_text'] = 'Bad version'

    return out


def combine_resources(v4only_data, nat64_data, v6only_data):
    resources = []
    if v4only_data:
        merge_resources(resources, v4only_data.get('resources', {}).values(), 'v4only')
    if v6only_data:
        merge_resources(resources, v6only_data.get('resources', {}).values(), 'v6only')
    if nat64_data:
        merge_resources(resources, nat64_data.get('resources', {}).values(), 'nat64')
    return resources


def merge_resources(resources, new_resources, key):
    last_found_index = None

    for new_resource in new_resources:
        try:
            # Extract data
            method = new_resource['method']
            url = new_resource['url']

            data = {
                'status': new_resource.get('status', 0),
                'error': new_resource.get('error', False),
                'timed_out': new_resource.get('timedOut', False),
                'location': '',
            }
            data.update(http_code_data(data['status'], data['error'], data['timed_out']))

            for header in new_resource.get('headers', []):
                if header.get('name', '').lower() == 'location':
                    data['location'] = header.get('value')
                    break

            found_index = None
            for index in range(len(resources)):
                if resources[index]['method'] == method and resources[index]['url'] == url:
                    found_index = index
                    break

            if found_index is not None:
                # Merge with existing record
                resources[found_index][key] = data
                last_found_index = found_index
            else:
                # No existing record, put new record after the last found record
                if last_found_index is not None:
                    resources.insert(last_found_index + 1, {
                        'method': method,
                        'url': url,
                        key: data
                    })
                    last_found_index += 1
                else:
                    # No previous found record, append at the end
                    resources.append({
                        'method': method,
                        'url': url,
                        key: data
                    })
                    last_found_index = len(resources) - 1

        except KeyError:
            # No method or no URL: skip
            pass
