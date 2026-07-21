import fetch from 'node-fetch';

async function createFacebookLiveEvent() {
  const pageId = process.env.FB_PAGE_ID;
  const accessToken = process.env.FB_PAGE_ACCESS_TOKEN;

  const url = `https://graph.facebook.com/${pageId}/live_videos`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: "Sacred Heart Catholic Church Livestream",
      description: "Automated livestream event created by Cloud Run",
      status: "SCHEDULED",   // or "LIVE_NOW"
      planned_start_time: Math.floor(Date.now() / 1000) + 600 // 10 minutes from now
    })
  });

  const data = await response.json();
  console.log("Facebook Live Event Response:", data);
  return data;
}
