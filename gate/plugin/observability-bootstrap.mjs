/* Initialize manual OTel before OpenClaw can claim the global providers. */
try{
 const {preloadObservability}=await import('./observability.mjs');
 preloadObservability({env:process.env,gitCommit:process.env.SANCTUM_GIT_COMMIT});
}catch{}
