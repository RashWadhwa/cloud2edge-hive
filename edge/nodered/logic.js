'use strict';

function number(value, min, max, name) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
        throw new Error(`invalid_${name}`);
    }
    return value;
}

function label(value, name) {
    if (typeof value !== 'string' || !/^[a-zA-Z0-9_-]{1,64}$/.test(value)) {
        throw new Error(`invalid_${name}`);
    }
    return value;
}

function indoor(payload, now = Date.now()) {
    if (!payload || typeof payload !== 'object' || !payload.reading) throw new Error('invalid_envelope');
    if (!['bme280', 'simulated'].includes(payload.source)) throw new Error('invalid_source');
    const r = payload.reading;
    const temperature = number(r.temperature, -40, 85, 'temperature');
    const humidity = number(r.humidity, 0, 100, 'humidity');
    const pressure = number(r.pressure, 300, 1100, 'pressure_hpa');
    const fields = {temperature, humidity, pressure};
    if (humidity > 0) {
        const gamma = Math.log(humidity / 100) + 17.62 * temperature / (243.12 + temperature);
        fields.dew_point = 243.12 * gamma / (17.62 - gamma);
    }
    return line(fields, {
        source: payload.source,
        sensor_id: label(payload.sensor_id, 'sensor_id'),
        location: label(payload.location, 'location'),
    }, now, now);
}

function weather(payload, location, now = Date.now()) {
    const current = payload && payload.current;
    if (!current || typeof current.time !== 'string') throw new Error('invalid_weather');
    // API request explicitly asks for timezone=GMT. Accept only that UTC shape.
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(current.time)) throw new Error('invalid_weather_time');
    const validTime = Date.parse(current.time + 'Z');
    if (!Number.isFinite(validTime) || validTime > now + 300000 || now - validTime > 3 * 3600000) {
        throw new Error('weather_time_out_of_range');
    }
    const units = payload.current_units || {};
    if (units.temperature_2m !== '°C' || units.relative_humidity_2m !== '%' || units.surface_pressure !== 'hPa') {
        throw new Error('unexpected_weather_units');
    }
    return line({
        temperature: number(current.temperature_2m, -100, 65, 'weather_temperature'),
        humidity: number(current.relative_humidity_2m, 0, 100, 'weather_humidity'),
        pressure: number(current.surface_pressure, 300, 1100, 'weather_pressure'),
    }, {source: 'open_meteo', sensor_id: 'weather-model', location: label(location, 'weather_location')}, validTime, now);
}

function line(fields, tags, validTime, receivedTime) {
    // All tag values have passed label validation or are fixed constants.
    const tagText = Object.entries(tags).map(([k, v]) => `${k}=${v}`).join(',');
    const fieldText = Object.entries({...fields, ingested_at: receivedTime / 1000})
        .map(([k, v]) => `${k}=${v}`).join(',');
    // Millisecond precision avoids JS integer overflow of nanosecond timestamps.
    return `environment,${tagText} ${fieldText} ${Math.trunc(validTime)}`;
}

function weatherUrl(env) {
    if (env.WEATHER_ENABLED !== 'true') return null;
    if (!env.WEATHER_LATITUDE?.trim() || !env.WEATHER_LONGITUDE?.trim()) throw new Error('weather_location_missing');
    const lat = number(Number(env.WEATHER_LATITUDE), -90, 90, 'latitude');
    const lon = number(Number(env.WEATHER_LONGITUDE), -180, 180, 'longitude');
    return 'https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon +
        '&current=temperature_2m,relative_humidity_2m,surface_pressure&timezone=GMT';
}

module.exports = {indoor, weather, weatherUrl};
