'use strict';

var page = require('webpage').create(),
    system = require('system'),
    address, proxy_host, proxy_port;

// Check command line arguments
if (system.args.length < 3 || system.args.length > 4) {
    console.log('Usage: render_page.js URL PROXY_HOST [PROXY_PORT]');
    phantom.exit(1);
}

// Process command line arguments
address = system.args[1];
proxy_host = system.args[2];
if (system.args.length >= 4) {
    proxy_port = system.args[3];
} else {
    proxy_port = 80;
}

// Set up proxy
phantom.setProxy(proxy_host, proxy_port, 'http', '', '');

// Set up page
function init_page(new_page) {
    page.viewportSize = {
        width: 1024,
        height: 1024
    };
    page.clipRect = {
        left: 0,
        top: 0,
        width: page.viewportSize.width,
        height: page.viewportSize.height
    };
    page.customHeaders = {
        "DNT": "1"
    };
    page.resourceTimeout = 5000;
    page.onResourceTimeout = function () {
    };
    page.onConsoleMessage = function () {
    };
    page.onError = function () {
    };
    page.onAlert = function () {
    };
    page.onConfirm = function () {
        return true;
    };
    page.onPrompt = function () {
        return '';
    };
    page.onPageCreated = function (created_page) {
        init_page(created_page);
    };
}
init_page(page);

// Open and render to stdout when done
page.open(address, function (status) {
    // system.stderr.writeLine(JSON.stringify(page));
    if (status !== 'success' || page.title == '502 Proxy Error' || page.plainText == '') {
        phantom.exit(1);
    } else {
        // Set a background color, because the default is transparent
        page.evaluate(function () {
            document.body.bgColor = 'white';
        });

        window.setTimeout(function () {
            try {
                page.render('/dev/stdout', {format: 'png', quality: '0'});
            } catch (e) {
                phantom.exit(1);
            }
            phantom.exit(0);
        }, 100);
    }
});
