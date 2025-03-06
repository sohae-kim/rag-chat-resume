const path = require('path');

module.exports = {
    experimental: {
        outputFileTracingRoot: path.join(__dirname),
        outputFileTracingIncludes: {
            '/api/**/*': ['./data/**/*']
        }
    }
}; 