'use strict';

var page = require('webpage').create(),
    system = require('system'),
    output = {
        'success': false,
        'status': '',
        'image': null,
        'resources': {}
    },
    screenshotTimer = null,
    abandonHopeTimer = null,
    address;

// Check command line arguments
if (system.args.length != 2) {
    console.log('Usage: render_page.js URL');
    phantom.exit(1);
}

// Process command line arguments
address = system.args[1];

function capitalize(s) {
    return s && s[0].toUpperCase() + s.slice(1);
}

// Create a snapshot
function takeScreenshot() {
    try {
        // Prevent transparent background
        page.evaluate(function () {
            document.body.bgColor = 'white';
        });

        output.image = page.renderBase64('png');
        console.log(JSON.stringify(output));
        phantom.exit(0);
    } catch (e) {
        output.status = 'render error';
        console.log(JSON.stringify(output));
        phantom.exit(1);
    }
}

// If all else fails
function abandonHope() {
    output.status = 'abandoned';
    console.log(JSON.stringify(output));
    phantom.exit(1);
}

// Set up page
function init_page(newPage) {
    newPage.viewportSize = {
        width: 1024,
        height: 1024
    };
    newPage.clipRect = {
        left: 0,
        top: 0,
        width: newPage.viewportSize.width,
        height: newPage.viewportSize.height
    };
    newPage.customHeaders = {
        "DNT": "1"
    };
    newPage.settings.resourceTimeout = 30000;
    newPage.onResourceRequested = function (data) {
        // Don't include the data from data URLs
        var url = data.url;
        if (url.split(':')[0] == 'data') {
            url = url.split(';')[0];
        }

        output.resources[data.id] = {
            "method": data.method,
            "url": url,
            "requestTime": data.time,
            "stage": "start",
            "error": false,
            "timedOut": false,
        };

        // Reset the screenshot timer if necessary
        if (screenshotTimer) {
            clearTimeout(screenshotTimer);
            screenshotTimer = setTimeout(takeScreenshot, 500);
        }
    };
    newPage.onResourceReceived = function (data) {
        output.resources[data.id]['bodySize'] = data.bodySize;
        output.resources[data.id]['contentType'] = data.contentType;
        output.resources[data.id]['headers'] = data.headers;
        output.resources[data.id]['stage'] = data.stage;
        output.resources[data.id]['status'] = data.status;

        var timeName = 'response' + capitalize(data.stage) + 'Time';
        output.resources[data.id][timeName] = data.time;

        // Reset the screenshot timer if necessary
        if (screenshotTimer) {
            clearTimeout(screenshotTimer);
            screenshotTimer = setTimeout(takeScreenshot, 500);
        }
    };
    newPage.onResourceError = function (data) {
        output.resources[data.id]['error'] = true;
        output.resources[data.id]['errorCode'] = data.errorCode;
    };
    newPage.onResourceTimeout = function (data) {
        output.resources[data.id]['timedOut'] = true;
    };
    newPage.onConsoleMessage = function (msg) {
    };
    newPage.onError = function (msg, trace) {
    };
    newPage.onAlert = function () {
    };
    newPage.onConfirm = function () {
        return true;
    };
    newPage.onPrompt = function () {
        return '';
    };
    newPage.onPageCreated = function (createdPage) {
        init_page(createdPage);
    };
}
init_page(page);

// Fallback
abandonHopeTimer = setTimeout(abandonHope, 45000);

// Open and render to stdout when done
page.open(address, function (status) {
    // Set (very rough) status in output
    output.status = status;

    if (status !== 'success') {
        console.log(JSON.stringify(output));
        phantom.exit(1);
    } else if (page.title == '502 Proxy Error' || output.resources[1].error) {
        // Override status for this special case
        output.status = 'proxy error';
        console.log(JSON.stringify(output));
        phantom.exit(1);
    } else {
        output.success = true;

        // We have hope (and a new timer coming up)
        clearTimeout(abandonHopeTimer);

        // Set a timer for the screenshot. Further network activity will delay the timer to allow the page to finish.
        screenshotTimer = setTimeout(takeScreenshot, 500);
    }
});
