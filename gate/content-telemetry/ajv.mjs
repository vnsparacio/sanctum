import {createRequire} from 'node:module';

// Source tests resolve dependencies from this checkout. Installed gate modules
// live beneath the external private prefix, so setup renders the reviewed
// package.json path and resolves the same pinned dependency from the source
// runtime instead of depending on ambient NODE_PATH behavior.
const packageFile='@SANCTUM_PACKAGE@';
const require=createRequire(packageFile.startsWith('@')?import.meta.url:packageFile);
const loaded=require('ajv');

export default loaded.default??loaded;
