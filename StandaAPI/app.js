var createError = require('http-errors');
var express = require('express');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');

var indexRouter = require('./routes/index');
var usersRouter = require('./routes/users');

const simpleGit = require("simple-git");
const git = simpleGit("/home/marcusedward/Desktop/STANDA");

var app = express();


// view engine setup
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'jade');

app.use(logger('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.use('/', indexRouter);
app.use('/users', usersRouter);

app.get('/commits', (req, res) => {
  if (!req.query.since) {
    res.status(400).json({error:"Not specified since"})
    return;
  }

  // Query parameters for branch, since, and until
  const branch = req.query.branch || 'main'; // If no branch query param, default to 'main'
  //const since = new Date(req.query.since * 1000).toISOString();
  const since = "2014-02-12T16:36:00-07:00";
  const until = new Date().toISOString();

  // Fetch the changes from the remote repository
  git.fetch().then(() => {
      // After the fetch is done, checkout to the specified branch
      console.log("checking out "+branch )
      return git.checkout(branch);
  })
  .then(() => {
      // After the checkout is done, get the logs
      git.log(["--since",since,"--until",until] ,(err, log) => {
          if (err) {
              console.log(err)
              res.status(500).send({error: 'An error occurred while getting the commits.'});
              return;
          }

          const commits = log.all.map(commit => ({
              message: commit.message,
              date: commit.date
          }));

          res.json(commits);
      });
  })
  .catch(err => {
      res.status(500).send({error: 'An error occurred while fetching the changes or checking out the branch.'});
  });
});


// catch 404 and forward to error handler
app.use(function(req, res, next) {
  next(createError(404));
});

// error handler
app.use(function(err, req, res, next) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get('env') === 'development' ? err : {};

  // render the error page
  res.status(err.status || 500);
  res.render('error');
});

module.exports = app;
