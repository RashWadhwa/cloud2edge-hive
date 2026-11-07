'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const logic = require('../nodered/logic');
const now = Date.parse('2026-11-07T12:10:00Z');
const indoor = () => ({source: 'bme280', sensor_id: 'arduino-1', location: 'indoor',
    reading: {temperature: 22, humidity: 50, pressure: 1013.25}});
const weather = () => ({current: {time: '2026-11-07T12:00', temperature_2m: 10,
    relative_humidity_2m: 80, surface_pressure: 1008}, current_units: {
    temperature_2m: '°C', relative_humidity_2m: '%', surface_pressure: 'hPa'}});

test('indoor conversion preserves source, uses ingestion timestamp and calculates dew point', () => {
    const line = logic.indoor(indoor(), now);
    assert.match(line, /^environment,source=bme280,sensor_id=arduino-1,location=indoor /);
    assert.match(line, /dew_point=11\./);
    assert.ok(line.endsWith(' ' + now));
});
test('rejects invalid measurements including wrong pressure units and nonfinite values', () => {
    for (const [field, value] of [['temperature', NaN], ['temperature', '22'], ['humidity', 101],
        ['humidity', null], ['pressure', 101325], ['pressure', Infinity]]) {
        const input = indoor(); input.reading[field] = value;
        assert.throws(() => logic.indoor(input, now));
    }
});
test('rejects line protocol tag injection and unrecognised source', () => {
    const input = indoor(); input.sensor_id = 'bad,source=trusted';
    assert.throws(() => logic.indoor(input, now));
    input.sensor_id = 'safe'; input.source = 'weather';
    assert.throws(() => logic.indoor(input, now));
});
test('simulation remains explicitly labelled and zero humidity has no infinite dew point', () => {
    const input = indoor(); input.source = 'simulated'; input.reading.humidity = 0;
    const line = logic.indoor(input, now);
    assert.match(line, /source=simulated/); assert.ok(!line.includes('dew_point'));
});
test('weather stores model valid time, never current fetch time', () => {
    const line = logic.weather(weather(), 'outdoor-estimate', now);
    assert.ok(line.endsWith(' ' + Date.parse('2026-11-07T12:00:00Z')));
    assert.match(line, /ingested_at=1794053400/);
    assert.match(line, /source=open_meteo/);
});
test('repeated weather fetch preserves valid-time age', () => {
    const a = logic.weather(weather(), 'outdoor', now).split(' ').at(-1);
    const b = logic.weather(weather(), 'outdoor', now + 600000).split(' ').at(-1);
    assert.equal(a, b);
});
test('rejects stale, future, invalid-unit and incomplete weather', () => {
    const old = weather(); old.current.time = '2026-11-06T12:00';
    const future = weather(); future.current.time = '2026-11-08T12:00';
    const units = weather(); units.current_units.temperature_2m = '°F';
    for (const input of [old, future, units, {}, null]) assert.throws(() => logic.weather(input, 'outside', now));
});
test('weather disabled means no API request; enabled requires bounded coordinates', () => {
    assert.equal(logic.weatherUrl({WEATHER_ENABLED: 'false'}), null);
    assert.throws(() => logic.weatherUrl({WEATHER_ENABLED: 'true', WEATHER_LATITUDE: '', WEATHER_LONGITUDE: ''}));
    assert.throws(() => logic.weatherUrl({WEATHER_ENABLED: 'true', WEATHER_LATITUDE: '91', WEATHER_LONGITUDE: '0'}));
    assert.match(logic.weatherUrl({WEATHER_ENABLED: 'true', WEATHER_LATITUDE: '51.5', WEATHER_LONGITUDE: '-0.1'}),
        /^https:\/\/api\.open-meteo\.com\/v1\/forecast\?/);
});
test('all flow wires resolve to real nodes and every serial success passes through storage', () => {
    const flows = require('../nodered/flows.json');
    const ids = new Set(flows.map(n => n.id));
    for (const node of flows) for (const output of node.wires || []) for (const id of output) assert.ok(ids.has(id), id);
    assert.equal(flows.find(n => n.id === 'validate').wires[0][0], 'influx-prepare');
});
