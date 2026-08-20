import { Amplify } from 'aws-amplify';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'eu-north-1_hVIR8C6l5',
      userPoolClientId: '3a3f1jain8aistg3rq35q3jv8i',
      loginWith: {
         email:true,
      },
    },
  },
});