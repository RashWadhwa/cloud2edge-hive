'use strict';
const fs = require('fs');
const crypto = require('crypto');
const read = name => fs.readFileSync('/run/secrets/' + name, 'utf8').trim();
const auth = JSON.parse(read('nodered_auth.json'));
const user = {username: 'admin', permissions: '*'};

module.exports = {
    flowFile: 'flows.json',
    flowFilePretty: true,
    credentialSecret: read('nodered_credential_key'),
    uiHost: '0.0.0.0',
    uiPort: 1880,
    apiMaxLength: '16kb',
    adminAuth: {
        type: 'credentials',
        users: username => Promise.resolve(username === user.username ? user : null),
        authenticate: (username, password) => {
            const candidate = crypto.scryptSync(password, auth.salt, 32);
            const expected = Buffer.from(auth.hash, 'hex');
            return Promise.resolve(username === user.username && crypto.timingSafeEqual(candidate, expected) ? user : null);
        },
    },
    httpNodeMiddleware: (req, res, next) => {
        if (Number(req.headers['content-length'] || 0) > 4096) return res.sendStatus(413);
        next();
    },
    functionGlobalContext: {
        edge: require('/opt/edge/logic.js'),
        ingestToken: read('ingest_token'),
        influxWriteToken: read('influx_write_token'),
        equalToken: (a, b) => {
            const x = Buffer.from(a || ''), y = Buffer.from(b);
            return x.length === y.length && crypto.timingSafeEqual(x, y);
        },
    },
    functionExternalModules: false,
    logging: {console: {level: 'info', metrics: false, audit: true}},
};
