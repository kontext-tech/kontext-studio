export default {
   preset: "ts-jest/presets/default-esm",
   extensionsToTreatAsEsm: [".ts"],
   moduleNameMapper: {
      "^(\\.{1,2}/.*)\\.js$": "$1"
   },
   testEnvironment: "node",
   testMatch: [
      "<rootDir>/src/**/__tests__/**/*.test.ts",
      "<rootDir>/src/**/*.test.ts"
   ],
   collectCoverageFrom: [
      "src/**/*.ts",
      "!src/**/*.d.ts",
      "!src/**/__tests__/**"
   ],
   transform: {
      "^.+\\.tsx?$": [
         "ts-jest",
         {
            useESM: true
         }
      ]
   },
   moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
   testTimeout: 10000
};
