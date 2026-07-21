import express from 'express';
import fetch from 'node-fetch';

const app = express();
app.use(express.json());

// Health check
app.get('/', (req, res) => {
  res.send('SHCC Create Livestream Event is running on Cloud Run (Node.js 24)');
});

// Facebook Live creation helper
async function createFacebookLiveEvent() {
  const pageId = process.env.FB_PAGE_ID;
  const accessToken = process.env.FB_PAGE_ACCESS_TOKEN;

  const url = `https://graph.facebook.com/${pageId}/live_videos?access_token=${accessToken}`;

  // Build a valid planned start time (rounded + 15 minutes ahead)
  const now = Math.floor(Date.now() / 1000);
  const rounded = Math.floor(now / 60) * 60;
  const plannedStart = rounded + (15 * 60); // 15 minutes from now

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: "Sacred Heart Catholic Church Livestream",
      description: "Automated livestream event created by Cloud Run",
      status: "SCHEDULED_UNPUBLISHED",
      planned_start_time: plannedStart
    })
  });

  const data = await response.json();
  console.log("Facebook Live Event Response:", data);
  return data;
}

// Endpoint to trigger Facebook Live creation
app.post('/create-facebook-live', async (req, res) => {
  try {
    const result = await createFacebookLiveEvent();
    res.status(200).json(result);
  } catch (err) {
    console.error("Error creating Facebook Live event:", err);
    res.status(500).send("Failed to create Facebook Live event");
  }
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
