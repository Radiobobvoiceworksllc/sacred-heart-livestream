import express from 'express';

const app = express();
app.use(express.json());

// Health check
app.get('/', (req, res) => {
  res.send('SHCC Create Livestream Event is running on Cloud Run (Node.js 24)');
});

// Example POST endpoint for automation triggers
app.post('/trigger', (req, res) => {
  console.log('Received automation payload:', req.body);
  res.status(200).send('Trigger received');
});

// Cloud Run provides PORT via environment variable
const port = process.env.PORT || 8080;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
