/*
 * Copyright (C) 2017 Glyptodon, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/**
 * Main Guacamole UI namespace.
 * @namespace
 */
var GuacUI = GuacUI || {};

/**
 * Creates a new element having the given tagname and CSS class.
 */
GuacUI.createElement = function(tagname, classname) {
    var new_element = document.createElement(tagname);
    if (classname) new_element.className = classname;
    return new_element;
};

/**
 * Creates a new element having the given tagname, CSS class, and specified
 * parent element.
 */
GuacUI.createChildElement = function(parent, tagname, classname) {
    var element = GuacUI.createElement(tagname, classname);
    parent.appendChild(element);
    return element;
};

/**
 * Adds the given CSS class to the given element.
 */
GuacUI.addClass = function(element, classname) {

    // If supported, use native classlist for addClass()
    if (Node.classlist)
        element.classList.add(classname);

    // Otherwise, simply add new class via string manipulation
    else
        element.className += " " + classname;

};

/**
 * Removes the given CSS class from the given element.
 */
GuacUI.removeClass = function(element, classname) {

    // If supported, use native classlist for removeClass()
    if (Node.classlist)
        element.classList.remove(classname);

    // Otherwise, remove class via string manipulation
    else {

        // Filter out classes with given name
        element.className = element.className.replace(/([^ ]+)[ ]*/g,
            function(match, testClassname, spaces, offset, string) {

                // If same class, remove
                if (testClassname == classname)
                    return "";

                // Otherwise, allow
                return match;
                
            }
        );

    } // end if no classlist support

};

/**
 * Object describing the UI's level of audio support. If the user has request
 * that audio be disabled, this object will pretend that audio is not
 * supported.
 */
GuacUI.Audio = new (function() {

    var codecs = [
        'audio/ogg; codecs="vorbis"',
        'audio/mp4; codecs="mp4a.40.5"',
        'audio/mpeg; codecs="mp3"',
        'audio/webm; codecs="vorbis"',
        'audio/wav; codecs=1'
    ];

    var probably_supported = [];
    var maybe_supported = [];

    /**
     * Array of all supported audio mimetypes, ordered by liklihood of
     * working.
     */
    this.supported = [];

    // If sound disabled, we're done now.
    if (GuacamoleSessionStorage.getItem("disable-sound", false))
        return;
    
    // Build array of supported audio formats
    codecs.forEach(function(mimetype) {

        var audio = new Audio();
        var support_level = audio.canPlayType(mimetype);

        // Trim semicolon and trailer
        var semicolon = mimetype.indexOf(";");
        if (semicolon != -1)
            mimetype = mimetype.substring(0, semicolon);

        // Partition by probably/maybe
        if (support_level == "probably")
            probably_supported.push(mimetype);
        else if (support_level == "maybe")
            maybe_supported.push(mimetype);

    });

    // Add probably supported types first
    Array.prototype.push.apply(
        this.supported, probably_supported);

    // Prioritize "maybe" supported types second
    Array.prototype.push.apply(
        this.supported, maybe_supported);

})();

/**
 * Object describing the UI's level of video support.
 */
GuacUI.Video = new (function() {

    var codecs = [
        'video/ogg; codecs="theora, vorbis"',
        'video/mp4; codecs="avc1.4D401E, mp4a.40.5"',
        'video/webm; codecs="vp8.0, vorbis"'
    ];

    var probably_supported = [];
    var maybe_supported = [];

    /**
     * Array of all supported video mimetypes, ordered by liklihood of
     * working.
     */
    this.supported = [];
    
    // Build array of supported audio formats
    codecs.forEach(function(mimetype) {

        var video = document.createElement("video");
        var support_level = video.canPlayType(mimetype);

        // Trim semicolon and trailer
        var semicolon = mimetype.indexOf(";");
        if (semicolon != -1)
            mimetype = mimetype.substring(0, semicolon);

        // Partition by probably/maybe
        if (support_level == "probably")
            probably_supported.push(mimetype);
        else if (support_level == "maybe")
            maybe_supported.push(mimetype);

    });

    // Add probably supported types first
    Array.prototype.push.apply(
        this.supported, probably_supported);

    // Prioritize "maybe" supported types second
    Array.prototype.push.apply(
        this.supported, maybe_supported);

})();

/**
 * Interface object which displays the progress of a download, ultimately
 * becoming a download link once complete.
 * 
 * @constructor
 * @param {String} filename The name the file will have once complete.
 */
GuacUI.Download = function(filename) {

    /**
     * Reference to this GuacUI.Download.
     * @private
     */
    var guac_download = this;

    /**
     * The outer div representing the notification.
     * @private
     */
    var element = GuacUI.createElement("div", "download notification");

    /**
     * Title bar describing the notification.
     * @private
     */
    var title = GuacUI.createChildElement(element, "div", "title-bar");

    /**
     * Close button for removing the notification.
     * @private
     */
    var close_button = GuacUI.createChildElement(title, "div", "close");
    close_button.onclick = function() {
        if (guac_download.onclose)
            guac_download.onclose();
    };

    GuacUI.createChildElement(title, "div", "title").textContent =
        "File Transfer";

    GuacUI.createChildElement(element, "div", "caption").textContent =
        filename + " ";

    /**
     * Progress bar and status.
     * @private
     */
    var progress = GuacUI.createChildElement(element, "div", "progress");

    /**
     * Updates the content of the progress indicator with the given text.
     * 
     * @param {String} text The text to assign to the progress indicator.
     */
    this.updateProgress = function(text) {
        progress.textContent = text;
    };

    /**
     * Updates the content of the dialog to reflect an error condition
     * represented by the given text.
     * 
     * @param {String} text A human-readable description of the error.
     */
    this.showError = function(text) {

        element.removeChild(progress);
        GuacUI.addClass(element, "error");

        var status = GuacUI.createChildElement(element, "div", "status");
        status.textContent = text;

    };

    /**
     * Removes the progress indicator and replaces it with a download button.
     */
    this.complete = function() {

        element.removeChild(progress);
        GuacUI.addClass(element, "complete");

        var download = GuacUI.createChildElement(element, "button");
        download.textContent = "Download";
        download.onclick = function() {
            if (guac_download.ondownload)
                guac_download.ondownload();
        };

    };

    /**
     * Returns the element representing this notification.
     */
    this.getElement = function() {
        return element;
    };

    /**
     * Called when the close button of this notification is clicked.
     * @event
     */
    this.onclose = null;

    /**
     * Called when the download button of this notification is clicked.
     * @event
     */
    this.ondownload = null;

};

/**
 * Interface object which displays the progress of a upload.
 * 
 * @constructor
 * @param {String} filename The name the file will have once complete.
 */
GuacUI.Upload = function(filename) {

    /**
     * Reference to this GuacUI.Upload.
     * @private
     */
    var guac_upload = this;

    /**
     * The outer div representing the notification.
     * @private
     */
    var element = GuacUI.createElement("div", "upload notification");

    /**
     * Title bar describing the notification.
     * @private
     */
    var title = GuacUI.createChildElement(element, "div", "title-bar");

    /**
     * Close button for removing the notification.
     * @private
     */
    var close_button = GuacUI.createChildElement(title, "div", "close");
    close_button.onclick = function() {
        if (guac_upload.onclose)
            guac_upload.onclose();
    };

    GuacUI.createChildElement(title, "div", "title").textContent =
        "File Transfer";

    GuacUI.createChildElement(element, "div", "caption").textContent =
        filename + " ";

    /**
     * Progress bar and status.
     * @private
     */
    var progress = GuacUI.createChildElement(element, "div", "progress");

    /**
     * The actual moving bar within the progress bar.
     * @private
     */
    var bar = GuacUI.createChildElement(progress, "div", "bar");

    /**
     * The textual readout of progress.
     * @private
     */
    var progress_status = GuacUI.createChildElement(progress, "div");

    /**
     * Updates the content of the progress indicator with the given text.
     * 
     * @param {String} text The text to assign to the progress indicator.
     * @param {Number} percent The overall percent complete.
     */
    this.updateProgress = function(text, percent) {
        progress_status.textContent = text;
        bar.style.width = percent + "%";
    };

    /**
     * Updates the content of the dialog to reflect an error condition
     * represented by the given text.
     * 
     * @param {String} text A human-readable description of the error.
     */
    this.showError = function(text) {

        element.removeChild(progress);
        GuacUI.addClass(element, "error");

        var status = GuacUI.createChildElement(element, "div", "status");
        status.textContent = text;

    };

    /**
     * Returns the element representing this notification.
     */
    this.getElement = function() {
        return element;
    };

    /**
     * Called when the close button of this notification is clicked.
     * @event
     */
    this.onclose = null;

};
