var hepdata_record = (function () {

    var preserve_abstract_line_wrap = function () {
      var abstract_html = $(".record-abstract-content").html();
      if (abstract_html) $(".record-abstract-content").html(abstract_html.trim());
    };

    var initialise_clipboard = function (selector) {
      new Clipboard(selector);
    };

    return {
      initialise: function () {
        MathJax.Hub.Config({
          tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
        });
        MathJax.Hub.Queue(["Typeset", MathJax.Hub]);

        preserve_abstract_line_wrap();
        initialise_clipboard('.copy-btn');
      },

      perform_upload_action: function (placement, form_name, colors, insertion_type) {
        if (event) {
          event.preventDefault();
        }

        var form = document.forms[form_name];
        var upload_size = $('input[name="hep_archive"]')[0].files[0].size;
        if (upload_size > HEPDATA.upload_max_size) {
          var message = '<p>Your submission of size ' + Math.round(upload_size/1024/1024) + ' MB is too large to be uploaded.</p>';
          message += '<p>Please reduce the size of your upload file to less than ' + Math.round(HEPDATA.upload_max_size/1024/1024) + ' MB and try again.</p>';
          message += '<p>Please contact info@hepdata.net if you need any further information.</p>';
          message += '<p><a href="" onclick="window.location.reload(false);">Try again</a></p>';
          var html = '<div id="upload-message">' + message + '</div>';
          $(".upload-form").css('display', 'none');
          $(placement).append(html);
          return;
        }

        var message = '<p>Uploading file...</p>'
        message += '<p>(Timeout after ' + Math.round(HEPDATA.upload_timeout/60) + ' minutes.)</p>';
        var html = '<div id="upload-progress"></div>' +
          '<div id="upload-message">' + message + '</div>';
        if (insertion_type === 'large_area') {
          html = '<div id="upload-progress"></div>' +
            '<div style="width: 300px; margin: 0 auto;" id="upload-message"><p>' + message + '</p></div>';
        }

        $(".upload-form").css('display', 'none');

        $(placement).append(html);

        if (colors === undefined) {
          colors = ["#955BA5", "white"]
        }

        HEPDATA.render_loader("#upload-progress", [
            {x: 26, y: 30, color: colors[0]},
            {x: -60, y: 55, color: colors[1]},
            {x: 37, y: -10, color: colors[0]},
            {x: -60, y: 10, color: colors[0]},
            {x: -27, y: -30, color: colors[0]},
            {x: 60, y: -55, color: colors[1]}],
          {"width": 200, "height": 200}
        );

        var data = new FormData(form);

		    $.ajax({
            type: "POST",
            enctype: 'multipart/form-data',
            url: form.action,
            data: data,
            dataType: "text json",
            processData: false,
            contentType: false,
            cache: false,
            timeout: HEPDATA.upload_timeout * 1000,
            success: function (data) {
              window.location.href = data['url'];
            },
            error: function (e, statusCode, text) {
              message = "<p>We were unable to upload your file.</p>";

              if (e.statusText == "timeout") {
                message += "<p>Your submission was too large to be uploaded within the timeout limit of " + Math.round(HEPDATA.upload_timeout/60)+ " minutes.</p>";
                message += "<p>Please reduce the size of your upload file and try again.</p>";
                message += "<p>Please contact info@hepdata.net if you need any further information.</p>";
              } else if (e.responseJSON && e.responseJSON['message']) {
                message += "<p>" + e.responseJSON['message'] + "</p>";
              } else {
                message += "<p>An unexpected error occurred. Please try again later, or contact info@hepdata.net if the message persists.</p>";
                message += "<p>Error details: " + e.status + " " + text + "</p>";
              }

              message += '<p><a href="" onclick="window.location.reload(false);">Try again</a></p>'

              $('#upload-progress').remove();
              $('#upload-message').html(message)
            }
        });

      }
    }
  }
)();
