@Library(['srePipeline']) _

// --------------------------------------------
// Refer to Pipeline docs for options used in mysettings
// https://wwwin-github.cisco.com/pages/eti/sre-pipeline-library
// --------------------------------------------

def pipelinesettings = [
  deploy: [
    [name: "aquarius" ]    // Containers to publish
  ],

  prepare: 1,                       // GIT Clone
  unittest: 1,                      // Unit-test
  build: 1,                         // Build Docker
  tagversion: "${env.BUILD_ID}",                // Docker tag version
  lint: 1,                          // Lint
//  forceBlackduck: 1,                // Force Blackduck Scan on any branch
//  blackduck: [
//    email: "eti-sre-admins@cisco.com",
//  ],                                // Blackduck Open Source Scan
  stricterCCThreshold: 90.0,        // Fail builds for Code Coverage below 90%

]

srePipeline( pipelinesettings )

