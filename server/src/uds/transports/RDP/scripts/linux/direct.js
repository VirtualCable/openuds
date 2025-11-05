'use strict';

// Info for lintering tools about the variables provided by uds client
var Process, Logger, File, Utils, Tasks;

// We receive data in "data" variable, which is an object from json readonly
var data;


const errorString = `You need to have xfreerdp or Thincast installed and in path for this to work.</p>
    <p>Please, install the proper package for your system.</p>
    <ul>
        <li>xfreerdp: <a href="https://github.com/FreeRDP/FreeRDP">Download</a></li>
        <li>Thincast: <a href="https://thincast.com/en/products/client">Download</a></li>
    </ul>`;

// Try, in order of preference, to find other RDP clients
const executablePath =
    Process.findExecutable('thincast-remote-desktop-client') ||
    Process.findExecutable('thincast-client') ||
    Process.findExecutable('thincast') ||
    Process.findExecutable('udsrdp') ||
    Process.findExecutable('xfreerdp3') ||
    Process.findExecutable('xfreerdp') ||
    Process.findExecutable('xfreerdp');

if (!executablePath) {
    Logger.error('No RDP client found on system');
    throw new Error('No RDP client found on system');
}

// using Utils.expandVars, expand variables of data.freerdp_params (that is an array of strings)
let parameters = data.freerdp_params.map((param) => Utils.expandVars(param));

let process = null;

// If has the as_file property, create the temp file on home folder and use it
if (data.as_file) {
    Logger.debug('Has as_file property, creating temp RDP file');
    // Create and save the temp file
    rdpFilePath = File.createTempFile(File.getHomeDirectory(), data.as_file, '.rdp');
    Logger.debug(`RDP temp file created at ${rdpFilePath}`);

    // Append to removable task to delete the file later
    Tasks.addEarlyUnlinkableFile(rdpFilePath);
    let password = data.password ? `/p:${data.password}` : '';
    // Launch the RDP client with the temp file
    process = Process.launch(executablePath, [rdpFilePath, password]);  // the addres in INSIDE the file is already set to
} else {
    // Launch the RDP client with the parameters
    process = Process.launch(executablePath, [...parameters, `/v:${data.address}`]);
}

Tasks.addWaitableApp(process);