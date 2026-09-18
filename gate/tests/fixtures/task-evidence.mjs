// Explicit synthetic host evidence; never used by production.
export const syntheticProtection=async({scope})=>({schema:'sanctum-task-evidence/v1',taskId:scope,integrity:'PASS',snapshotDigest:'a'.repeat(64),contractDigest:'b'.repeat(64),candidateDigest:'c'.repeat(64),acceptanceRequired:false,protectedCount:0});
