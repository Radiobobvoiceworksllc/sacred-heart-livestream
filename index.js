app.post('/create-facebook-live', async (req, res) => {
  try {
    const result = await createFacebookLiveEvent();
    res.status(200).json(result);
  } catch (err) {
    console.error("Error creating Facebook Live event:", err);
    res.status(500).send("Failed to create Facebook Live event");
  }
});
